"""Append exact loopback workspace callbacks without changing accounts or grants."""

from dotenv import dotenv_values

from scripts.configure_registration import ORIGIN, ROOT, provider_session


def configure():
    values = dotenv_values(ROOT / ".env")
    base = ORIGIN + "/admin/realms/student-support/clients"
    with provider_session(values) as http:
        for client_id, port in [("support-local", 5050), ("support-test", 5051)]:
            response = http.get(base, params={"clientId": client_id}, timeout=5)
            response.raise_for_status()
            rows = response.json()
            if len(rows) != 1:
                raise ValueError("Provision the two local identity clients first.")
            client = rows[0]
            callbacks = [
                f"http://127.0.0.1:{port}{prefix}/auth/callback"
                for prefix in ["", "/student", "/university"]
            ]
            client["redirectUris"] = list(
                dict.fromkeys([*client.get("redirectUris", []), *callbacks])
            )
            response = http.put(base + "/" + client["id"], json=client, timeout=5)
            response.raise_for_status()
    print("Exact local student/university callbacks configured; accounts and grants preserved.")


if __name__ == "__main__":
    try:
        configure()
    except Exception:
        raise SystemExit("Local workspace setup failed; no sensitive details printed.") from None
