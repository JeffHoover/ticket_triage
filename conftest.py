# This file is intentionally empty.
#
# When pytest finds a conftest.py in a directory, it adds that directory to
# sys.path. Placing this file at the project root lets tests do
# `from ticket_triage.coordinator import ...` without any packaging setup.
#
# Alternatives if you outgrow this: a pyproject.toml with
# [tool.pytest.ini_options] pythonpath = ["."], or an editable install
# (pip install -e .) once the package is properly configured.
