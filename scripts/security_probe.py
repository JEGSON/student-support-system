"""Small explicit active HTTP probe, restricted to the evaluation loopback origin."""

import argparse
import hashlib
import json
import re
import secrets
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from dotenv import dotenv_values

from app.repositories.core import utc_now
from app.repositories.fixtures import fixture_id
from scripts.database_setup import ROOT, local_client


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    origin = "http://127.0.0.1:5052"
    values = dotenv_values(ROOT / ".env")
    client = local_client(values, "testing")
    db = client.student_support_test
    actor, case_id, sid = str(uuid4()), str(uuid4()), str(uuid4())
    token = secrets.token_urlsafe(32)
    now = utc_now()
    results = []
    http = requests.Session()
    http.cookies.set("support_session", token, domain="127.0.0.1", path="/")
    db.users.insert_one(
        {
            "_id": actor,
            "identity_issuer": values["OIDC_ISSUER"],
            "identity_subject": "dast/" + actor,
            "display_name": "Synthetic DAST student",
            "account_status": "active",
            "global_roles": ["student"],
            "authorization_revision": 0,
            "created_at": now,
        }
    )
    db.sessions.insert_one(
        {
            "_id": sid,
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "user_id": actor,
            "created_at": now,
            "last_seen_at": now,
            "idle_expires_at": now + timedelta(minutes=30),
            "absolute_expires_at": now + timedelta(hours=8),
            "authentication_time": now,
            "data": {"context": "student"},
            "version": 0,
        }
    )
    db.cases.insert_one(
        {
            "_id": case_id,
            "reference": "DAST-" + case_id[:12],
            "student_id": actor,
            "category": "finance",
            "description": "Synthetic DAST request",
            "team_id": fixture_id("team_finance"),
            "assignee_id": None,
            "status": "New",
            "priority": "standard",
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "archive_state": "active",
            "legal_hold": False,
        }
    )

    def check(name, method, path, status, **kwargs):
        assert path.startswith("/") and not path.startswith("//")
        response = http.request(method, origin + path, allow_redirects=False, timeout=10, **kwargs)
        results.append(
            {
                "probe": name,
                "expected": status,
                "observed": response.status_code,
                "passed": response.status_code == status,
            }
        )
        return response

    try:
        page = check("authorised own case", "GET", "/cases/" + case_id, 200)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]
        response = check("foreign ownership", "GET", "/cases/" + fixture_id("case_b"), 404)
        other = check("missing case indistinguishable", "GET", "/cases/" + str(uuid4()), 404)
        results.append(
            {"probe": "uniform denied response body", "passed": response.content == other.content}
        )
        check("malformed identifier", "GET", "/cases/%24ne", 404)
        check("operator cursor", "GET", "/cases?after[$ne]=null", 400)
        check("forged host", "GET", "/", 400, headers={"Host": "attacker.invalid"})
        check(
            "forwarded host injection",
            "GET",
            "/",
            400,
            headers={"X-Forwarded-Host": "attacker.invalid"},
        )
        check("forwarded proto injection", "GET", "/", 400, headers={"X-Forwarded-Proto": "https"})
        check("student staff workspace denied", "GET", "/staff", 403)
        check("student admin denied", "GET", "/access", 403)
        check("student retention denied", "GET", "/retention", 403)
        check("notes in student URL rejected", "GET", "/staff/cases/" + case_id, 403)
        check(
            "missing CSRF",
            "POST",
            "/cases/" + case_id + "/message",
            400,
            data={"body": "Synthetic CSRF attack", "version": "1"},
        )
        check(
            "operator JSON body",
            "POST",
            "/cases/new",
            400,
            json={"category": {"$ne": None}},
            headers={"X-CSRFToken": csrf},
        )
        form = http.get(origin + "/cases/new", timeout=10)
        key = re.search(r'name="submission_key" value="([^"]+)"', form.text)[1]
        base = {
            "csrf_token": csrf,
            "submission_key": key,
            "category": "finance",
            "description": "Synthetic probe",
        }
        check(
            "forged ownership",
            "POST",
            "/cases/new",
            400,
            data={**base, "student_id": fixture_id("student_a")},
        )
        check("forged status", "POST", "/cases/new", 400, data={**base, "status": "Closed"})
        check(
            "oversized body",
            "POST",
            "/cases/new",
            413,
            data=b"x" * (128 * 1024 + 1),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        check("unsafe method", "PUT", "/cases/" + case_id, 405)
        xss = "Synthetic probe <script>window.DAST=true</script>"
        sent = check(
            "stored script accepted as plain text",
            "POST",
            "/cases/new",
            303,
            data={**base, "description": xss},
        )
        shown = http.get(origin + sent.headers["Location"], allow_redirects=False, timeout=10)
        results.append(
            {
                "probe": "stored script escaped and CSP blocks script execution",
                "passed": "<script>" not in shown.text
                and "&lt;script&gt;" in shown.text
                and "script-src 'none'" in shown.headers.get("Content-Security-Policy", ""),
            }
        )
        for name in [
            "Cache-Control",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
        ]:
            results.append(
                {"probe": "security header " + name, "passed": bool(shown.headers.get(name))}
            )
        report = {
            "scope": origin + " application only; no provider/SMTP scanning",
            "tool": "project-owned explicit HTTP negative probe v1; not a comprehensive pentest",
            "checks": results,
            "passed": sum(bool(r["passed"]) for r in results),
            "failed": sum(not r["passed"] for r in results),
        }
        (ROOT / "docs/evidence/stage-16/security-probe.json").write_text(
            json.dumps(report, indent=2)
        )
        print("Scoped HTTP checks:", report["passed"], "passed;", report["failed"], "failed")
        assert not report["failed"]
    finally:
        ids = [r["_id"] for r in db.cases.find({"student_id": actor}, {"_id": 1})]
        for name in ["messages", "internal_notes", "case_events", "notification_outbox"]:
            db[name].delete_many({"case_id": {"$in": ids}})
        db.submission_keys.delete_many({"user_id": actor})
        db.audit_events.delete_many({"actor_id": actor})
        db.sessions.delete_many({"user_id": actor})
        db.cases.delete_many({"_id": {"$in": ids}})
        db.users.delete_one({"_id": actor})
        client.close()
        http.close()


if __name__ == "__main__":
    main()
