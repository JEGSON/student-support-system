"""Enable student sign-up only in the synthetic loopback Keycloak realm."""

import os
import tempfile
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "http://127.0.0.1:8180"


def provider_session(values):
    if values.get("APP_ENV") != "development" or values.get("OIDC_ISSUER") != (
        ORIGIN + "/realms/student-support"
    ):
        raise ValueError("Local synthetic identity configuration only.")
    http = requests.Session()
    http.trust_env = False
    try:
        response = http.post(
            ORIGIN + "/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "synthetic_bootstrap",
                "password": values["OIDC_ADMIN_PASSWORD"],
            },
            timeout=5,
        )
        response.raise_for_status()
        http.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        return http
    except Exception:
        http.close()
        raise


def configure():
    env_path = ROOT / ".env"
    original = env_path.read_text()
    values = dotenv_values(env_path)
    base = ORIGIN + "/admin/realms/student-support"
    with provider_session(values) as http:
        response = http.get(base + "/users/profile", timeout=5)
        response.raise_for_status()
        profile = response.json()
        email = next(row for row in profile["attributes"] if row["name"] == "email")
        email.setdefault("validations", {})["pattern"] = {"pattern": r"^[^@\s]+@example\.invalid$"}
        email.setdefault("annotations", {})["inputHelperTextBefore"] = (
            "Synthetic details only: use an address ending in @example.invalid."
        )
        response = http.put(base + "/users/profile", json=profile, timeout=5)
        response.raise_for_status()
        response = http.put(
            base,
            json={
                "registrationAllowed": True,
                "registrationEmailAsUsername": False,
                "duplicateEmailsAllowed": False,
                "resetPasswordAllowed": False,
                "verifyEmail": False,
                "passwordPolicy": "length(12) and upperCase(1) and lowerCase(1) and digits(1)",
                "bruteForceProtected": True,
            },
            timeout=5,
        )
        response.raise_for_status()
    if env_path.read_text() != original:
        raise ValueError("Configuration changed concurrently; rerun without overwriting it.")
    lines = [
        line for line in original.splitlines() if not line.startswith("SELF_REGISTRATION_ENABLED=")
    ]
    content = "\n".join([*lines, "SELF_REGISTRATION_ENABLED=1", ""])
    with tempfile.NamedTemporaryFile(mode="w", dir=ROOT / "runtime", delete=False) as out:
        temporary = Path(out.name)
        os.fchmod(out.fileno(), 0o600)
        out.write(content)
    try:
        os.replace(temporary, env_path)
    finally:
        temporary.unlink(missing_ok=True)
    print("Local student registration enabled; reserved email domain enforced. Restart the app.")


if __name__ == "__main__":
    try:
        configure()
    except Exception:
        raise SystemExit(
            "Local registration configuration failed; sensitive details suppressed."
        ) from None
