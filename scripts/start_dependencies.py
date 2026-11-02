"""Start the named isolated stack and initialise its replica set, without secrets in argv."""
from pathlib import Path
import subprocess
import time
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
from app import create_app

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker','compose','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'infrastructure/compose.yaml')]


def main():
    if not (ROOT/'.env').exists():
        raise SystemExit('Run python3 scripts/setup_local.py first.')
    subprocess.run(COMPOSE+['up','-d'], cwd=ROOT, check=True)
    script = (ROOT/'infrastructure/bootstrap-mongo.js').read_text()
    # Do not print bootstrap stderr; database errors may include connection details.
    for attempt in range(45):
        result = subprocess.run(COMPOSE+['exec','-T','mongo','mongosh','--quiet','--nodb','--file','/dev/stdin'],
                                input=script, text=True, capture_output=True, cwd=ROOT)
        if result.returncode == 0 and 'users ready' in result.stdout:
            print('Replica set and isolated development/test users ready.')
            app = create_app(dict(dotenv_values(ROOT/'.env')))
            try:
                deadline = time.monotonic() + 90
                with app.app_context():
                    while time.monotonic() < deadline:
                        try:
                            if all(check() for check in app.extensions['readiness_checks']):
                                print('All required local dependencies are ready.')
                                return
                        except Exception:
                            pass
                        time.sleep(1)
            finally:
                app.extensions['mongo'].close()
            raise SystemExit('Required local dependencies did not become ready.')
        time.sleep(1)
    raise SystemExit('Local database bootstrap failed. Inspect local service state without sharing credentials.')


if __name__ == '__main__':
    main()
