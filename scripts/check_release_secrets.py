"""Check release candidates against actual local private secrets without printing them."""

import argparse
import json
import subprocess
import zipfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env")
    secrets = {
        v.encode()
        for k, v in values.items()
        if v
        and len(v) >= 12
        and ("PASSWORD" in k or "SECRET" in k or k.endswith("_KEY") or k.endswith("_KEYS"))
    }
    for key, value in values.items():
        if key.endswith("_KEYS") and value:
            try:
                secrets.update(
                    v.encode() for v in json.loads(value) if isinstance(v, str) and len(v) >= 12
                )
            except (ValueError, TypeError):
                pass
    credentials = ROOT / "runtime/synthetic-logins.json"
    if credentials.exists():
        secrets.update(
            row["password"].encode() for row in json.loads(credentials.read_text()).values()
        )
    if not secrets:
        raise SystemExit("No private comparison values available; do not claim a verified scan.")
    if args.archive:
        with zipfile.ZipFile(args.archive) as z:
            entries = [(p, z.read(p)) for p in z.namelist() if not p.endswith("/")]
    else:
        names = (
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
            )
            .decode()
            .split("\0")
        )
        entries = [(p, (ROOT / p).read_bytes()) for p in set(names) if p and (ROOT / p).is_file()]
    failures = []
    for name, body in entries:
        if (
            any(secret in body for secret in secrets)
            or (b"-----BEGIN " + b"PRIVATE KEY-----") in body
        ):
            failures.append(name)
    if failures:
        print(json.dumps({"failed_paths": failures}))
        raise SystemExit(1)
    print(
        json.dumps(
            {"files_checked": len(entries), "secret_values_checked": len(secrets), "matches": 0}
        )
    )


if __name__ == "__main__":
    main()
