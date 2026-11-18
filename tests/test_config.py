"""Регрессия: веб-приложение требует явные настройки доступа."""
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def startup_env():
    env = os.environ.copy()
    env["STROYMIR_ADMIN_PASSWORD"] = secrets.token_urlsafe(24)
    env["STROYMIR_SECRET_KEY"] = secrets.token_hex(32)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


@pytest.mark.parametrize("missing", ["STROYMIR_ADMIN_PASSWORD", "STROYMIR_SECRET_KEY"])
def test_startup_rejects_missing_credentials(missing):
    env = startup_env()
    env.pop(missing, None)
    result = subprocess.run([sys.executable, "-c", "import app"], cwd=ROOT, env=env,
                            capture_output=True, text=True, errors="replace")
    assert result.returncode != 0
    assert missing in result.stderr


def test_configured_app_starts_without_database_connection():
    result = subprocess.run(
        [sys.executable, "-c",
         "import app; assert app.app.test_client().get('/admin').status_code == 302"],
        cwd=ROOT, env=startup_env(), capture_output=True, text=True, errors="replace")
    assert result.returncode == 0, result.stderr
