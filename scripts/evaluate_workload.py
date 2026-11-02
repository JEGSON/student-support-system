"""Authorised fixed synthetic workload. Local test DB and loopback Gunicorn only."""

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from itsdangerous import URLSafeTimedSerializer

from app.operations.recovery import capture, restore
from app.repositories.core import utc_now
from app.repositories.fixtures import fixture_id
from app.repositories.schema import SCHEMAS, install_schema
from scripts.database_setup import ROOT, local_client


def percentile(values, p):
    ordered = sorted(values)
    return (
        round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))] * 1000, 2)
        if ordered
        else None
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--cases", type=int, default=20000)
    parser.add_argument("--messages", type=int, default=100000)
    parser.add_argument("--users", type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 900 or not 1 <= args.users <= 50:
        raise ValueError("Bounded synthetic evaluation only.")
    values = dict(dotenv_values(ROOT / ".env"))
    if values.get("APP_ENV") != "development":
        raise ValueError("Local setup required.")
    output = ROOT / "docs/evidence/stage-16"
    output.mkdir(parents=True, exist_ok=True)
    client = local_client(values, "testing")
    db = client.student_support_test
    run = uuid4().hex
    now = utc_now()
    user_ids = [str(uuid4()) for _ in range(args.users)]
    case_ids = [str(uuid4()) for _ in range(args.cases)]
    session_ids = []
    tokens = [secrets.token_urlsafe(32) for _ in user_ids]
    server = None
    logs = None
    web = local_client(values, "web_testing")
    try:
        db.users.insert_many(
            [
                {
                    "_id": uid,
                    "identity_issuer": values["OIDC_ISSUER"],
                    "identity_subject": "load/" + run + "/" + str(i),
                    "display_name": "Synthetic load user " + str(i),
                    "account_status": "active",
                    "global_roles": ["student"],
                    "authorization_revision": 0,
                    "created_at": now,
                }
                for i, uid in enumerate(user_ids)
            ]
        )
        cases = [
            {
                "_id": cid,
                "reference": "LOAD-" + run[:8] + "-" + str(i),
                "student_id": user_ids[i % args.users],
                "category": "finance",
                "description": "Synthetic workload request. " * 6,
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
            for i, cid in enumerate(case_ids)
        ]
        db.cases.insert_many(cases)
        for start in range(0, args.messages, 2000):
            db.messages.insert_many(
                [
                    {
                        "_id": str(uuid4()),
                        "case_id": case_ids[i % args.cases],
                        "author_id": user_ids[(i % args.cases) % args.users],
                        "author_context": "student",
                        "body": "Synthetic workload message. " * 6,
                        "created_at": now,
                    }
                    for i in range(start, min(start + 2000, args.messages))
                ]
            )
        for uid, token in zip(user_ids, tokens, strict=True):
            sid = str(uuid4())
            session_ids.append(sid)
            db.sessions.insert_one(
                {
                    "_id": sid,
                    "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                    "user_id": uid,
                    "created_at": now,
                    "last_seen_at": now,
                    "idle_expires_at": now + timedelta(minutes=30),
                    "absolute_expires_at": now + timedelta(hours=8),
                    "authentication_time": now,
                    "data": {"context": "student"},
                    "version": 0,
                }
            )
        env = {k: str(v) for k, v in os.environ.items()}
        # Pass only web settings from the private setup, never operator passwords.
        for key in [
            "SECRET_KEY",
            "OIDC_ISSUER",
            "OIDC_CLIENT_ID",
            "EMAIL_HEALTH_URL",
            "CASE_ROUTING_JSON",
        ]:
            if values.get(key):
                env[key] = values[key]
        env.update(
            APP_ENV="testing",
            MONGODB_DATABASE="student_support_test",
            MONGODB_URI=web.address
            and values["MONGODB_URI"]
            .replace("support_app:", "support_web_test:")
            .replace(values["MONGO_APP_PASSWORD"], values["MONGO_WEB_TEST_PASSWORD"]),
            APP_BASE_URL="http://127.0.0.1:5052",
            FLASK_DEBUG="0",
            RATE_LIMIT_ENABLED="1",
            RATE_LIMIT_READ="600",
            RATE_LIMIT_WRITE="120",
        )
        logs = (ROOT / "runtime/performance-gunicorn.log").open("w")
        server = subprocess.Popen(
            [
                str(ROOT / ".venv/bin/gunicorn"),
                "--config",
                "gunicorn.conf.py",
                "--bind",
                "127.0.0.1:5052",
                "wsgi:application",
            ],
            cwd=ROOT,
            env=env,
            stdout=logs,
            stderr=logs,
        )
        for _ in range(100):
            try:
                if requests.get("http://127.0.0.1:5052/health/live", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Evaluation server unavailable.")
        started = time.monotonic()
        deadline = started + args.seconds
        progress = [started]

        def user(index):
            http = requests.Session()
            http.cookies.set("support_session", tokens[index], domain="127.0.0.1", path="/")
            cid = case_ids[index]
            url = "http://127.0.0.1:5052/cases/" + cid
            first = http.get(url, timeout=15)
            first.raise_for_status()
            csrf = re.search(r'name="csrf_token" value="([^"]+)"', first.text)[1]
            signer = URLSafeTimedSerializer(values["SECRET_KEY"], salt="case-submission-v1")
            durations = []
            reads = []
            writes = []
            errors = {}
            version = 1
            step = 0
            counts = {"read": 0, "write": 0}
            while time.monotonic() < deadline:
                is_read = (step % 10) < 7
                method = "read" if is_read else "write"
                t = time.monotonic()
                status = 0
                try:
                    if is_read:
                        selected = case_ids[
                            index
                            + ((step // 10) % max(1, (args.cases - index) // args.users))
                            * args.users
                        ]
                        response = http.get("http://127.0.0.1:5052/cases/" + selected, timeout=15)
                        status = response.status_code
                    else:
                        key = signer.dumps(
                            {"user": user_ids[index], "nonce": secrets.token_urlsafe(32)}
                        )
                        response = http.post(
                            url + "/message",
                            data={
                                "csrf_token": csrf,
                                "submission_key": key,
                                "version": str(version),
                                "body": "Synthetic load reply. " * 8,
                            },
                            allow_redirects=False,
                            timeout=15,
                        )
                        status = response.status_code
                        if status == 303:
                            version += 1
                    if status not in {200, 303}:
                        errors[str(status)] = errors.get(str(status), 0) + 1
                except requests.RequestException:
                    errors["transport"] = errors.get("transport", 0) + 1
                duration = time.monotonic() - t
                durations.append(duration)
                (reads if is_read else writes).append(duration)
                counts[method] += 1
                step += 1
                if index == 0 and time.monotonic() - progress[0] >= 30:
                    progress[0] = time.monotonic()
                    print(
                        json.dumps(
                            {
                                "elapsed_s": round(time.monotonic() - started),
                                "sample_user_p95_ms": percentile(durations, 0.95),
                                "sample_errors": errors,
                            }
                        ),
                        flush=True,
                    )
                time.sleep(max(0, 0.5 - duration))
            http.close()
            return durations, reads, writes, errors, counts

        print(
            json.dumps(
                {
                    "phase": "running",
                    "seconds": args.seconds,
                    "cases": args.cases,
                    "messages": args.messages,
                    "users": args.users,
                }
            ),
            flush=True,
        )
        with ThreadPoolExecutor(max_workers=args.users) as pool:
            results = list(pool.map(user, range(args.users)))
        elapsed = time.monotonic() - started
        all_times = []
        read_times = []
        write_times = []
        errors = {}
        counts = {"read": 0, "write": 0}
        for durations, reads, writes, failures, numbers in results:
            all_times += durations
            read_times += reads
            write_times += writes
            for key, n in failures.items():
                errors[key] = errors.get(key, 0) + n
            for key, n in numbers.items():
                counts[key] += n
        plans = {}
        for name, query, sort, hint in [
            (
                "cases",
                {"student_id": user_ids[0], "archive_state": "active"},
                [("updated_at", -1), ("_id", -1)],
                "cases_v1_6",
            ),
            (
                "messages",
                {"case_id": case_ids[0]},
                [("created_at", -1), ("_id", -1)],
                "messages_v1_1",
            ),
        ]:
            plan = db.command(
                "explain",
                {
                    "find": name,
                    "filter": query,
                    "sort": dict(sort),
                    "limit": 21 if name == "cases" else 50,
                    "hint": hint,
                },
                verbosity="executionStats",
            )
            plans[name] = {
                "nReturned": plan["executionStats"]["nReturned"],
                "totalDocsExamined": plan["executionStats"]["totalDocsExamined"],
                "totalKeysExamined": plan["executionStats"]["totalKeysExamined"],
                "winningPlan": plan["queryPlanner"]["winningPlan"],
            }
        report = {
            "dataset": {
                "cases": args.cases,
                "starting_messages": args.messages,
                "users": args.users,
                "request_description_characters": len(cases[0]["description"]),
                "seed_message_characters": len("Synthetic workload message. " * 6),
            },
            "configuration": {
                "server": "Gunicorn 26.2.0",
                "workers": 2,
                "threads_per_worker": 8,
                "mongo_pool_per_worker": 20,
                "think_time_seconds": 0.5,
                "read_limit_per_minute": 600,
                "write_limit_per_minute": 120,
                "oidc_and_smtp_excluded": True,
                "payload": "synthetic text only",
            },
            "duration_seconds": round(elapsed, 3),
            "requests": len(all_times),
            "counts": counts,
            "read_percent": round(100 * counts["read"] / len(all_times), 2),
            "p50_ms": percentile(all_times, 0.5),
            "p95_ms": percentile(all_times, 0.95),
            "read_p95_ms": percentile(read_times, 0.95),
            "write_p95_ms": percentile(write_times, 0.95),
            "throughput_rps": round(len(all_times) / elapsed, 2),
            "errors": errors,
            "unexpected_error_percent": round(100 * sum(errors.values()) / len(all_times), 4),
            "targets": {
                "p95_below_2000ms": percentile(all_times, 0.95) < 2000,
                "unexpected_errors_below_1pct": sum(errors.values()) / len(all_times) < 0.01,
            },
            "plans": plans,
        }
        hardware = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string", "hw.memsize", "hw.logicalcpu"],
            capture_output=True,
            text=True,
        )
        report["hardware"] = hardware.stdout.strip().splitlines()
        (output / "workload.json").write_text(json.dumps(report, indent=2, default=str))
        print(
            json.dumps(
                {
                    "phase": "workload_complete",
                    **{k: report[k] for k in ["requests", "p95_ms", "throughput_rps", "errors"]},
                }
            ),
            flush=True,
        )
        # Recovery on the actual measured dataset, after the timed load interval.
        key = Fernet.generate_key()
        directory = ROOT / "runtime" / ("recovery-load-" + run)
        directory.mkdir()
        capture_started = time.monotonic()
        meta = capture(db, key, directory / "backup.enc")
        capture(db, key, directory / "ledger.enc", True)
        with local_client(values, "schema") as schema:
            install_schema(schema.student_support_restore_test)
        with local_client(values, "restore") as restore_client:
            target = restore_client.student_support_restore_test
            if any(target[name].find_one({}) for name in SCHEMAS):
                raise RuntimeError("Quarantine must be empty.")
            restore_started = time.monotonic()
            recovered = restore(target, key, directory / "backup.enc", directory / "ledger.enc")
            restore_elapsed = time.monotonic() - restore_started
            recovered["restored_cases"] = target.cases.count_documents({})
            recovered["restored_messages"] = target.messages.count_documents({})
            for name in SCHEMAS:
                target[name].delete_many({})
        (output / "workload-recovery.json").write_text(
            json.dumps(
                {
                    "backup_and_ledger_seconds": round(restore_started - capture_started, 3),
                    "restore_seconds": round(restore_elapsed, 3),
                    "snapshot_age_at_restore_seconds": round(
                        (
                            utc_now()
                            - __import__("datetime").datetime.fromisoformat(meta["captured_at"])
                        ).total_seconds(),
                        3,
                    ),
                    **meta,
                    **recovered,
                },
                indent=2,
            )
        )
        print("Recovery measurement completed; quarantine cleaned.", flush=True)
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        if logs:
            logs.close()
        for name in [
            "messages",
            "internal_notes",
            "case_events",
            "notification_outbox",
            "triage_claims",
        ]:
            db[name].delete_many({"case_id": {"$in": case_ids}})
        db.referrals.delete_many({"source_case_id": {"$in": case_ids}})
        db.submission_keys.delete_many({"user_id": {"$in": user_ids}})
        db.audit_events.delete_many({"actor_id": {"$in": user_ids}})
        db.sessions.delete_many({"user_id": {"$in": user_ids}})
        db.cases.delete_many({"_id": {"$in": case_ids}})
        db.users.delete_many({"_id": {"$in": user_ids}})
        client.close()
        web.close()


if __name__ == "__main__":
    main()
