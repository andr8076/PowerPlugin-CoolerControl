#!/usr/bin/env python3
"""CoolerControl device plugin exposing power-derived virtual temperatures."""
from __future__ import annotations

from concurrent import futures
import logging
import os
from pathlib import Path
import signal
import socket
import stat
import sys
import threading
import time

import grpc

# The generated protobuf modules contain absolute imports of "coolercontrol".
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "generated"))
from coolercontrol.device_service.v1 import (  # noqa: E402
    device_service_pb2_grpc,
    health_pb2,
    initialize_device_pb2,
    list_devices_pb2,
    reset_channel_pb2,
    shutdown_pb2,
    status_pb2 as response_status_pb2,
)
from coolercontrol.models.v1 import (  # noqa: E402
    device_pb2,
    device_info_pb2,
    status_pb2 as reading_status_pb2,
    temp_info_pb2,
)
from power_sensor import Source, discover, read_limits, virtual_temp

SERVICE_ID = "cc_power_to_temp"
VERSION = "1.0.0-rc.4"
DEVICE_ID = "virtual_power"
SOCKET = Path(os.environ.get("CC_POWER_SOCKET", "/run/cc-power-to-temp.sock"))
CONFIG = BASE / "config.json"
log = logging.getLogger("cc_power_to_temp")


class PowerService(device_service_pb2_grpc.DeviceServiceServicer):
    """Read-only CoolerControl device with one virtual temp per power source."""

    def __init__(self, sources: list[Source] | None = None, config_path: Path = CONFIG):
        self.sources = discover() if sources is None else sources
        self.config_path = Path(config_path)
        self.lock = threading.Lock()
        self.started_at = time.monotonic()
        self.bad_count = 0
        self.last_warning_at = 0.0

    def Health(self, request, context):
        # A missing max-watt setting is expected on first launch. The service
        # must stay connectable so its UI can configure those sources.
        healthy = bool(self.sources)
        return health_pb2.HealthResponse(
            name=SERVICE_ID,
            version=VERSION,
            status=(health_pb2.HealthResponse.STATUS_OK if healthy
                    else health_pb2.HealthResponse.STATUS_WARNING),
            uptime_seconds=max(0, int(time.monotonic() - self.started_at)),
        )

    def ListDevices(self, request, context):
        if not self.sources:
            return list_devices_pb2.ListDevicesResponse()
        temps = {
            source.channel_id: temp_info_pb2.TempInfo(
                label=f"{source.label} (power %)", number=i + 1,
            )
            for i, source in enumerate(self.sources)
        }
        return list_devices_pb2.ListDevicesResponse(devices=[
            device_pb2.Device(
                id=DEVICE_ID,
                name="Power to Temperature",
                uid_info="cc-power-to-temp-virtual-sensors",
                info=device_info_pb2.DeviceInfo(
                    temps=temps, temp_min=0.0, temp_max=100.0,
                    model="Power-based virtual temperature sensors",
                ),
            ),
        ])

    def InitializeDevice(self, request, context):
        return initialize_device_pb2.InitializeDeviceResponse()

    def Status(self, request, context):
        if request.device_id != DEVICE_ID:
            context.abort(grpc.StatusCode.NOT_FOUND, "Unknown virtual device")
        limits = read_limits(self.config_path)
        bad: list[str] = []
        with self.lock:
            readings = []
            for source in self.sources:
                watts = source.watts()
                maximum = limits.get(source.channel_id)
                if watts is None:
                    bad.append(f"{source.label}: unavailable power reading")
                elif maximum is None:
                    bad.append(f"{source.label}: maximum wattage not configured")
                readings.append(
                    reading_status_pb2.Status(
                        id=source.channel_id,
                        temp=virtual_temp(watts, maximum),
                    ),
                )
            self.bad_count = len(bad)

        now = time.monotonic()
        if bad and now - self.last_warning_at > 60:
            log.warning(
                "Fail-safe (100 virtual C) on %d source(s): %s.",
                len(bad), ", ".join(bad),
            )
            self.last_warning_at = now
        return response_status_pb2.StatusResponse(status=readings)

    def Shutdown(self, request, context):
        return shutdown_pb2.ShutdownResponse()

    def ResetChannel(self, request, context):
        return reset_channel_pb2.ResetChannelResponse()

    def _not_supported(self, context):
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Virtual sensors cannot control hardware")

    def EnableManualFanControl(self, request, context):
        return self._not_supported(context)

    def FixedDuty(self, request, context):
        return self._not_supported(context)

    def SpeedProfile(self, request, context):
        return self._not_supported(context)

    def Lighting(self, request, context):
        return self._not_supported(context)

    def Lcd(self, request, context):
        return self._not_supported(context)

    def CustomFunctionOne(self, request, context):
        return self._not_supported(context)


def _prepare_socket(path: Path) -> None:
    """Allow replacing a stale socket only in a directory owned by this service."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() and not path.is_socket():
        return
    metadata = path.lstat()
    if not stat.S_ISSOCK(metadata.st_mode):
        raise RuntimeError(f"Refusing to remove non-socket path: {path}")
    if metadata.st_uid != os.geteuid():
        raise RuntimeError(f"Refusing to remove socket owned by another user: {path}")
    # Do not steal an existing live service's socket.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as check:
        check.settimeout(0.5)
        if check.connect_ex(str(path)) == 0:
            raise RuntimeError(f"Service socket already in use: {path}")
    path.unlink()


def main() -> None:
    logging.basicConfig(level=os.environ.get("CC_LOG", "INFO").upper())
    svc = PowerService()
    log.info("Starting v%s with %d power source(s)", VERSION, len(svc.sources))
    for source in svc.sources:
        log.info("Source: %s (%s)", source.label, source.channel_id)
    if not svc.sources:
        log.warning("No hwmon/RAPL power sources found. Check kernel sensor support.")

    _prepare_socket(SOCKET)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    device_service_pb2_grpc.add_DeviceServiceServicer_to_server(svc, server)
    if not server.add_insecure_port(f"unix://{SOCKET}"):
        raise RuntimeError(f"Cannot bind service socket: {SOCKET}")
    server.start()

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        stop.wait()
    finally:
        server.stop(grace=2).wait()
        if SOCKET.is_socket() and SOCKET.lstat().st_uid == os.geteuid():
            SOCKET.unlink()
        log.info("Stopped")


if __name__ == "__main__":
    main()
