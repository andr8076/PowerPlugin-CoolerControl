# Contributing

Bug reports and pull requests are welcome. Please include your CoolerControl version, Linux distribution and kernel, relevant journalctl output, and whether the power sensor appears in the Linux sensors command.

Keep the code small and hardware-agnostic. Do not add direct fan writes or modify CoolerControl internals. Treat missing sensor data as a fail-safe state, never zero watts.

Run checks before submitting:

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/generate_proto.py
.venv/bin/python -m unittest discover -s tests -v
~~~

Do not commit local virtual environments, private configs, generated bindings, or machine-specific paths.
