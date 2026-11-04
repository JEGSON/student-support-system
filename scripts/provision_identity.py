"""Explicit loopback synthetic identity provisioning; never used by web requests."""

import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from dotenv import dotenv_values

from app.repositories.fixtures import fixture_documents
from scripts.configure_registration import configure
from scripts.configure_workspaces import configure as configure_workspaces
from scripts.database_setup import ROOT, local_client

ORIGIN = "http://127.0.0.1:8180"
REALM = "student-support"


def provision():
    values = dotenv_values(ROOT / ".env")
    if (
        values.get("APP_ENV") != "development"
        or values.get("OIDC_ISSUER") != ORIGIN + "/realms/" + REALM
    ):
        raise ValueError("Local development only.")
    private = ROOT / "runtime/synthetic-logins.json"
    credentials = json.loads(private.read_text()) if private.exists() else {}
    http = requests.Session()
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
    base = ORIGIN + "/admin/realms/" + REALM
    # An exact additional loopback callback allows isolated automated tests without
    # taking over a developer's running server on 5050.
    response = http.get(base + "/clients", params={"clientId": "support-test"}, timeout=5)
    response.raise_for_status()
    if not response.json():
        response = http.post(
            base + "/clients",
            json={
                "clientId": "support-test",
                "publicClient": True,
                "standardFlowEnabled": True,
                "directAccessGrantsEnabled": False,
                "redirectUris": [
                    f"http://127.0.0.1:5051{prefix}/auth/callback"
                    for prefix in ["", "/student", "/university"]
                ],
                "webOrigins": [],
                "attributes": {"pkce.code.challenge.method": "S256"},
            },
            timeout=5,
        )
        response.raise_for_status()
    for doc in fixture_documents(values["OIDC_ISSUER"])["users"]:
        name = doc["identity_subject"].split(":", 1)[1]
        username = "synthetic_" + name
        response = http.get(
            base + "/users", params={"username": username, "exact": "true"}, timeout=5
        )
        response.raise_for_status()
        users = response.json()
        if not users:
            password = secrets.token_urlsafe(24)
            # Persist the generated password privately before the provider write;
            # a retry can finish mapping without losing its generated credential.
            credentials[name] = {"username": username, "password": password}
            fd = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as out:
                json.dump(credentials, out, indent=2)
            response = http.post(
                base + "/users",
                json={
                    "username": username,
                    "enabled": True,
                    "firstName": "Synthetic",
                    "lastName": name,
                    "emailVerified": True,
                    "credentials": [{"type": "password", "value": password, "temporary": False}],
                },
                timeout=5,
            )
            response.raise_for_status()
            response = http.get(
                base + "/users", params={"username": username, "exact": "true"}, timeout=5
            )
            response.raise_for_status()
            users = response.json()
        response = http.put(
            base + "/users/" + users[0]["id"],
            json={
                "firstName": "Synthetic",
                "lastName": name,
                "email": username + "@example.invalid",
                "emailVerified": True,
                "requiredActions": [],
            },
            timeout=5,
        )
        response.raise_for_status()
        if len(users) != 1 or name not in credentials:
            raise ValueError("Explicit credential recovery required.")
        for environment in ("development", "testing"):
            with local_client(values, environment) as client:
                db = client[
                    "student_support_dev"
                    if environment == "development"
                    else "student_support_test"
                ]
                result = db.users.update_one(
                    {"_id": doc["_id"], "fixture_version": "synthetic-v1"},
                    {
                        "$set": {
                            "identity_subject": users[0]["id"],
                            "verified_contact": username + "@example.invalid",
                        }
                    },
                )
                if not result.matched_count:
                    raise ValueError("Seed isolated fixtures before provisioning.")
    http.close()
    configure_workspaces()
    configure()
    print(
        "Synthetic identities mapped. Credentials are private in runtime/synthetic-logins.json; no passwords printed."
    )


if __name__ == "__main__":
    try:
        provision()
    except Exception:
        raise SystemExit(
            "Local identity provisioning failed; sensitive details suppressed."
        ) from None
