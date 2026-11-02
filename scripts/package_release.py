"""Build a deterministic source ZIP from a clean local Git commit; never publish."""

import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", "runtime", "dist", "instance", "data", "backups", "__pycache__"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    if git("status", "--porcelain").strip():
        raise SystemExit("Commit/review source changes before packaging; the tree must be clean.")
    commit = git("rev-parse", "HEAD").decode().strip()
    stamp = datetime.fromtimestamp(int(git("show", "-s", "--format=%ct", "HEAD")), timezone.utc)
    entries = {}
    for value in git("ls-files", "-z").decode().split("\0"):
        if not value:
            continue
        path = Path(value)
        if (
            any(part in EXCLUDED for part in path.parts)
            or path.name == ".env"
            or (path.name.startswith(".env.") and path.name != ".env.example")
            or path.suffix in {".key", ".pem", ".log", ".dump", ".pyc"}
        ):
            raise SystemExit("Excluded private/generated path is tracked; review before release.")
        entries[value] = git("show", f"HEAD:{value}")
    manifest = {
        "source_commit": commit,
        "git_metadata_included": False,
        "history_review": "Retained local repository; no remote publication verified.",
        "sha256": {p: hashlib.sha256(b).hexdigest() for p, b in sorted(entries.items())},
    }
    entries["PACKAGE-MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    archive = output / "student-support-assessment.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path, body in sorted(entries.items()):
            info = zipfile.ZipInfo("student-support-system/" + path, stamp.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, body)
    receipt = {
        "source_commit": commit,
        "archive": archive.name,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "bytes": archive.stat().st_size,
        "files": len(entries),
        "git_metadata_included": False,
    }
    (output / "package-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (output / "SHA256SUMS").write_text(receipt["sha256"] + "  " + archive.name + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
