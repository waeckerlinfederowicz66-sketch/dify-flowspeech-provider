"""Create disposable CE settings and a fixture-only CA; never read host secrets."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parent


def prepare(state: Path) -> None:
    pins = json.loads((ROOT / "pins.json").read_text())
    package = state / "candidate.difypkg"
    if hashlib.sha256(package.read_bytes()).hexdigest() != pins["package_sha256"]:
        raise ValueError("The candidate is not the reviewed Marketplace artifact")
    if (state / "runtime.env").exists():
        raise ValueError("Use a fresh disposable state directory")
    os.umask(0o077)
    for name in ("evidence", "wheels"):
        (state / name).mkdir(exist_ok=True)
    password = secrets.token_hex(24)
    daemon_key, inner_key = secrets.token_hex(32), secrets.token_hex(32)
    settings = {
        "SECRET_KEY": secrets.token_hex(32), "DEPLOY_ENV": "PRODUCTION",
        "EDITION": "SELF_HOSTED", "DB_TYPE": "postgresql", "DB_HOST": "db",
        "DB_PORT": "5432", "DB_USERNAME": "postgres", "DB_PASSWORD": password,
        "DB_DATABASE": "dify", "DB_DEFAULT_DATABASE": "postgres", "DB_SSL_MODE": "disable",
        "POSTGRES_DB": "dify", "POSTGRES_USER": "postgres", "POSTGRES_PASSWORD": password,
        "REDIS_HOST": "redis", "REDIS_PORT": "6379", "REDIS_PASSWORD": "",
        "REDIS_DB": "0", "CELERY_BROKER_URL": "redis://redis:6379/1",
        "CONSOLE_API_URL": "http://api:5001", "CONSOLE_WEB_URL": "http://api:5001",
        "SERVICE_API_URL": "http://api:5001", "FILES_URL": "http://api:5001",
        "INTERNAL_FILES_URL": "http://api:5001", "APP_WEB_URL": "http://api:5001",
        "STORAGE_TYPE": "opendal", "OPENDAL_SCHEME": "fs", "OPENDAL_FS_ROOT": "storage",
        "PLUGIN_DAEMON_URL": "http://plugin_daemon:5002", "PLUGIN_DAEMON_KEY": daemon_key,
        "PLUGIN_DAEMON_TIMEOUT": "420", "INNER_API_KEY_FOR_PLUGIN": inner_key,
        "SERVER_HOST": "0.0.0.0", "SERVER_PORT": "5002", "SERVER_KEY": daemon_key,
        "SERVER_WORKER_AMOUNT": "1", "GUNICORN_TIMEOUT": "420",
        "APP_MAX_EXECUTION_TIME": "420", "WORKFLOW_MAX_EXECUTION_TIME": "420",
        "DIFY_INNER_API_URL": "http://api:5001", "DIFY_INNER_API_KEY": inner_key,
        "PLATFORM": "local", "PLUGIN_REMOTE_INSTALLING_ENABLED": "false",
        "PLUGIN_STORAGE_TYPE": "local", "PLUGIN_STORAGE_LOCAL_ROOT": "/app/storage",
        "PLUGIN_WORKING_PATH": "/app/storage/cwd", "PLUGIN_INSTALLED_PATH": "plugin",
        "PLUGIN_PACKAGE_CACHE_PATH": "plugin_packages", "PLUGIN_MEDIA_CACHE_PATH": "assets",
        "PERSISTENCE_STORAGE_PATH": "persistence", "PERSISTENCE_STORAGE_MAX_SIZE": "104857600",
        "PLUGIN_MAX_EXECUTION_TIMEOUT": "420", "PLUGIN_INSTALL_TIMEOUT": "8",
        "PLUGIN_LOCAL_LAUNCHING_CONCURRENT": "1", "ROUTINE_POOL_SIZE": "128",
        "LIFETIME_COLLECTION_HEARTBEAT_INTERVAL": "5", "LIFETIME_COLLECTION_GC_INTERVAL": "60",
        "LIFETIME_STATE_GC_INTERVAL": "300", "DIFY_INVOCATION_CONNECTION_IDLE_TIMEOUT": "420",
        "DIFY_BACKWARDS_INVOCATION_READ_TIMEOUT": "420000",
        "MAX_PLUGIN_PACKAGE_SIZE": "52428800", "MAX_BUNDLE_PACKAGE_SIZE": "52428800",
        "PYTHON_INTERPRETER_PATH": "/usr/bin/python3.12", "PYTHON_ENV_INIT_TIMEOUT": "300",
        "UV_PATH": "/usr/local/bin/uv", "ENABLE_OTEL": "false", "SENTRY_ENABLED": "false",
        "MARKETPLACE_ENABLED": "false", "SCARF_NO_ANALYTICS": "true",
        "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "*",
    }
    (state / "runtime.env").write_text("".join(f"{k}={v}\n" for k, v in settings.items()))
    fixture = {"api_key": "ce-fixture-" + secrets.token_hex(24),
               "control_key": secrets.token_hex(24), "password": "Gate9" + secrets.token_hex(16),
               "email": "ce-gate@example.com"}
    (state / "fixture.json").write_text(json.dumps(fixture))
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
        "-subj", "/CN=FlowSpeech isolated CE fixture",
        "-addext", "subjectAltName=DNS:flowspeech.io,DNS:static.flowspeech.io",
        "-keyout", str(state / "ca.key"), "-out", str(state / "ca.crt"),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (state / "evidence" / "pins.json").write_text(json.dumps(pins, indent=2) + "\n")
    print("Prepared isolated settings and fixture CA; no credentials printed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    prepare(parser.parse_args().state.resolve())
