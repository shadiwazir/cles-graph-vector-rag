"""Test session setup: tests must not write to the real MLflow server."""

import os

os.environ["MLFLOW_ENABLED"] = "false"
os.environ["AUDIT_ENVIRONMENT"] = (
    "test"  # integration tests write audit rows: keep them out of drift checks
)
