#!/usr/bin/env python3
"""Regenerate Python gRPC bindings from bundled CoolerControl proto sources."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "proto"
DESTINATION = ROOT / "generated"


def main() -> None:
    sources = sorted(p.relative_to(SOURCE) for p in SOURCE.rglob("*.proto"))
    if not sources:
        raise SystemExit("No bundled proto files found")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{SOURCE}",
        f"--python_out={DESTINATION}",
        f"--grpc_python_out={DESTINATION}",
        *map(str, sources),
    ], cwd=ROOT, check=True)
    print(f"Generated Python bindings for {len(sources)} CoolerControl proto files")


if __name__ == "__main__":
    main()
