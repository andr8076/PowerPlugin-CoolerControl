# Contributing

Bug reports and pull requests are welcome.

For sensor issues, include your Linux distribution, kernel version, CoolerControl version, the output of `sensors`, and relevant service logs.

## Running tests

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/generate_proto.py
.venv/bin/python -m unittest discover -s tests -v
```

Keep sensor backends read-only and return the fail-safe value when data is unavailable. Avoid committing local configuration, generated bindings or virtual environments.
