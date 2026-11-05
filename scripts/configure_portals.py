"""Configure separate loopback portal clients, preserving existing identity accounts."""

from dotenv import dotenv_values

from scripts.configure_registration import ORIGIN, ROOT, provider_session


def configure():
    values = dotenv_values(ROOT / ".env")
    base = ORIGIN + "/admin/realms/student-support"
    with provider_session(values) as http:
        response = http.get(base + "/authentication/flows", timeout=5)
        response.raise_for_status()
        browser_flow = next(row["id"] for row in response.json() if row["alias"] == "browser")
        for name, origin in [
            ("support-student", "http://127.0.0.1:5050"),
            ("support-staff", "http://localhost:5050"),
            ("support-student-test", "http://127.0.0.1:5051"),
            ("support-staff-test", "http://localhost:5051"),
        ]:
            response = http.get(base + "/clients", params={"clientId": name}, timeout=5)
            response.raise_for_status()
            rows = response.json()
            client = (
                rows[0]
                if rows
                else {
                    "clientId": name,
                    "publicClient": True,
                    "standardFlowEnabled": True,
                    "directAccessGrantsEnabled": False,
                    "webOrigins": [],
                    "attributes": {"pkce.code.challenge.method": "S256"},
                }
            )
            client["name"] = "Staff portal" if "staff" in name else "Student portal"
            client.setdefault("authenticationFlowBindingOverrides", {})["browser"] = browser_flow
            client.setdefault("attributes", {})["login_theme"] = "support-portals"
            client["redirectUris"] = [origin + "/auth/callback"]
            response = (
                http.put(base + "/clients/" + client["id"], json=client, timeout=5)
                if rows
                else http.post(base + "/clients", json=client, timeout=5)
            )
            response.raise_for_status()
        response = http.get(base, timeout=5)
        response.raise_for_status()
        realm = response.json()
        realm["displayName"] = "Student Support"
        response = http.put(base, json=realm, timeout=5)
        response.raise_for_status()
        response = http.get(base + "/users/profile", timeout=5)
        response.raise_for_status()
        profile = response.json()
        email = next(row for row in profile["attributes"] if row["name"] == "email")
        email.setdefault("validations", {})["pattern"] = {"pattern": r"^[^@\s]+@example\.invalid$"}
        email.setdefault("annotations", {}).pop("inputHelperTextBefore", None)
        response = http.put(base + "/users/profile", json=profile, timeout=5)
        response.raise_for_status()
    print(
        "Separate host-only portal clients configured. Existing users, passwords and roles preserved."
    )


if __name__ == "__main__":
    try:
        configure()
    except Exception:
        raise SystemExit(
            "Portal identity configuration failed; no private details printed."
        ) from None
