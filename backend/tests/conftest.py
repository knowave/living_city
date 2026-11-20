import os

# Must be set before app.core.config is imported so TestClient lifespans start no runners.
os.environ["RUNNER_ENABLED"] = "false"
