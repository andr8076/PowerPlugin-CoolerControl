import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from power_sensor import Source, discover, read_limits, virtual_temp
from service import PowerService


class PowerSensorTests(unittest.TestCase):
    def test_linear_mapping_and_clamp(self):
        self.assertEqual(virtual_temp(0, 500), 0)
        self.assertEqual(virtual_temp(100, 500), 20)
        self.assertEqual(virtual_temp(250, 500), 50)
        self.assertEqual(virtual_temp(500, 500), 100)
        self.assertEqual(virtual_temp(650, 500), 100)

    def test_fail_safe(self):
        for watts, ceiling in [(None, 500), (100, None), (-1, 500),
                               (100, 0), (float("nan"), 500)]:
            self.assertEqual(virtual_temp(watts, ceiling), 100)

    def test_power_hwmon(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "power1_average"
            p.write_text("125000000\n")
            s = Source("gpu", "GPU", p, "power_uw")
            self.assertEqual(s.watts(), 125)
            self.assertEqual(s.channel_id, Source("gpu","GPU",p,"power_uw").channel_id)
            p.write_text("-100")
            self.assertIsNone(s.watts())
            p.unlink()
            self.assertIsNone(s.watts())

    def test_rapl_time_and_wrap(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "energy_uj"
            r = Path(td) / "max_energy_range_uj"
            r.write_text("100000000")
            p.write_text("70000000")
            s = Source("cpu", "CPU", p, "energy_uj", r)
            self.assertIsNone(s.watts(1.0))
            p.write_text("85000000")
            self.assertEqual(s.watts(2.0), 15)
            p.write_text("5000000")
            self.assertEqual(s.watts(3.0), 20)  # wraps at 100M microjoules
            p.write_text("10000000")
            self.assertIsNone(s.watts(20.0))  # stale sampling

    def test_invalid_and_valid_config(self):
        with TemporaryDirectory() as td:
            f = Path(td) / "config.json"
            self.assertEqual(read_limits(f), {})
            f.write_text('{"max_watts":{"tempA":500,"tempB":0,"tempC":"oops"}}')
            self.assertEqual(read_limits(f), {"tempA":500})

    def test_detection_and_plugin_rpc(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            hm = root / "class/hwmon/hwmon2"
            hm.mkdir(parents=True)
            (hm / "name").write_text("amdgpu")
            (hm / "power1_average").write_text("250000000")
            (hm / "power1_label").write_text("PPT")
            rapl = root / "class/powercap/intel-rapl:0"
            rapl.mkdir(parents=True)
            (rapl / "name").write_text("package-0")
            (rapl / "energy_uj").write_text("10000000")
            (rapl / "max_energy_range_uj").write_text("100000000")
            sources = discover(root)
            self.assertEqual(len(sources), 2)
            self.assertEqual({s.label for s in sources}, {"amdgpu PPT", "CPU package-0 power"})
            limits_path = root / "config.json"
            limits_path.write_text(json.dumps({"max_watts": {s.channel_id: 500 for s in sources}}))
            plugin = PowerService(sources, config_path=limits_path)
            device = plugin.ListDevices(None,None).devices[0]
            self.assertEqual(len(device.info.temps),2)
            reply = plugin.Status(type("Q",(),{"device_id":"virtual_power"})(),None)
            vals = {x.id:x.temp for x in reply.status}
            gpu = next(s for s in sources if s.kind=="power_uw")
            self.assertEqual(vals[gpu.channel_id],50)
            cpu = next(s for s in sources if s.kind=="energy_uj")
            self.assertEqual(vals[cpu.channel_id],100)  # warm-up fails safe


if __name__ == "__main__":
    unittest.main()


class AdditionalTests(unittest.TestCase):
    def test_hwmon_average_preferred_and_inputs_supported(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "class/hwmon/hwmon12"
            folder.mkdir(parents=True)
            (folder / "name").write_text("example")
            (folder / "power1_input").write_text("30000000")
            (folder / "power1_average").write_text("42000000")
            (folder / "power2_input").write_text("25000000")
            sources = discover(root)
            self.assertEqual(len(sources), 2)
            self.assertEqual([s.watts() for s in sources], [42.0, 25.0])
            self.assertEqual(sources[0].path.name, "power1_average")
            self.assertEqual(sources[1].path.name, "power2_input")

    def test_power_limit_and_invalid_energy(self):
        with TemporaryDirectory() as temp:
            file = Path(temp) / "reading"
            file.write_text("10000000001")
            self.assertIsNone(Source("id", "device", file, "power_uw").watts())
            file.write_text("not a number")
            self.assertIsNone(Source("id", "device", file, "power_uw").watts())

    def test_health_allows_unconfigured_sources(self):
        with TemporaryDirectory() as temp:
            file = Path(temp) / "reading"
            file.write_text("10000000")
            source = Source("id", "device", file, "power_uw")
            config_path = Path(temp) / "config.json"
            service = PowerService([source], config_path)
            from coolercontrol.device_service.v1 import health_pb2
            health = service.Health(None, None)
            self.assertEqual(health.status, health_pb2.HealthResponse.STATUS_OK)
            config_path.write_text(json.dumps({"max_watts": {source.channel_id: 100}}))
            health = service.Health(None, None)
            self.assertEqual(health.status, health_pb2.HealthResponse.STATUS_OK)

    def test_grpc_socket_round_trip(self):
        import grpc
        from concurrent import futures
        from coolercontrol.device_service.v1 import device_service_pb2_grpc
        from coolercontrol.device_service.v1 import health_pb2, list_devices_pb2, status_pb2
        with TemporaryDirectory() as temp:
            sensor_path = Path(temp) / "power"
            sensor_path.write_text("200000000")
            source = Source("gpu-test", "Test GPU", sensor_path, "power_uw")
            config_path = Path(temp) / "config.json"
            config_path.write_text(json.dumps({"max_watts": {source.channel_id: 500}}))
            impl = PowerService([source], config_path)
            grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
            device_service_pb2_grpc.add_DeviceServiceServicer_to_server(impl, grpc_server)
            endpoint = "unix://" + str(Path(temp) / "plugin.sock")
            self.assertNotEqual(grpc_server.add_insecure_port(endpoint), 0)
            grpc_server.start()
            try:
                with grpc.insecure_channel(endpoint) as channel:
                    grpc.channel_ready_future(channel).result(timeout=3)
                    client = device_service_pb2_grpc.DeviceServiceStub(channel)
                    health = client.Health(health_pb2.HealthRequest(), timeout=3)
                    self.assertEqual(health.status, health_pb2.HealthResponse.STATUS_OK)
                    devices = client.ListDevices(list_devices_pb2.ListDevicesRequest(), timeout=3)
                    self.assertEqual(len(devices.devices), 1)
                    self.assertIn(source.channel_id, devices.devices[0].info.temps)
                    readings = client.Status(status_pb2.StatusRequest(device_id="virtual_power"), timeout=3)
                    self.assertEqual(readings.status[0].temp, 40.0)
            finally:
                grpc_server.stop(grace=0).wait()



class ConfigurationReloadTests(unittest.TestCase):
    def test_new_maximum_applies_to_running_service_without_restart(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            reading = folder / "power1_average"
            reading.write_text("250000000")
            source = Source("gpu-ppt", "Test GPU", reading, "power_uw")
            config_file = folder / "config.json"
            service = PowerService([source], config_file)
            request = type("Q", (), {"device_id": "virtual_power"})()

            # No configuration: full-scale fail-safe.
            self.assertEqual(service.Status(request, None).status[0].temp, 100)

            config_file.write_text(json.dumps({
                "max_watts": {source.channel_id: 500}
            }))
            self.assertEqual(service.Status(request, None).status[0].temp, 50)

            # Reconfigure while running, without recreating the service.
            config_file.write_text(json.dumps({
                "max_watts": {source.channel_id: 1000}
            }))
            self.assertEqual(service.Status(request, None).status[0].temp, 25)
