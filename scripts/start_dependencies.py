"""Start this project's isolated stack with bounded bootstrap/readiness waits."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values

from app import create_app
from scripts.prepare_schema_secret import prepare

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    str(ROOT / ".env"),
    "-f",
    str(ROOT / "infrastructure/compose.yaml"),
]


def bootstrap_database():
    script = (ROOT / "infrastructure/bootstrap-mongo.js").read_text()
    deadline = time.monotonic() + 90
    command = COMPOSE + [
        "exec",
        "-T",
        "mongo",
        "mongosh",
        "--quiet",
        "--nodb",
        "--file",
        "/dev/stdin",
    ]
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            # Error output can contain connection details; keep it out of routine logs.
            result = subprocess.run(
                command,
                input=script,
                text=True,
                capture_output=True,
                cwd=ROOT,
                timeout=min(10, remaining),
            )
        except subprocess.TimeoutExpired:
            continue
        if result.returncode == 0 and "users ready" in result.stdout:
            print("Replica set and isolated development/test users ready.")
            return
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise SystemExit("Local database bootstrap timed out. No credentials were printed.")


def wait_for_dependencies():
    app = create_app(dict(dotenv_values(ROOT / ".env")))
    try:
        deadline = time.monotonic() + 90
        with app.app_context():
            while time.monotonic() < deadline:
                try:
                    if all(check() for check in app.extensions["readiness_checks"]):
                        print("All required local dependencies are ready.")
                        return
                except Exception:
                    pass
                time.sleep(1)
    finally:
        app.extensions["mongo"].close()
    raise SystemExit("Required local dependencies did not become ready.")


def main():
    if not (ROOT / ".env").exists():
        raise SystemExit("Run python3 scripts/setup_local.py first.")
    prepare()
    try:
        subprocess.run(COMPOSE + ["up", "-d"], cwd=ROOT, check=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise SystemExit("Local dependency startup failed or timed out.") from None
    bootstrap_database()
    wait_for_dependencies()


if __name__ == "__main__":
    main()
