"""Add only the new schema-setup secret to an existing generated local setup."""
from pathlib import Path
import secrets
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]


def prepare():
    path=ROOT/'.env'
    if not path.exists():raise SystemExit('Generate local .env first.')
    if not dotenv_values(path).get('MONGO_SCHEMA_PASSWORD'):
        with path.open('a') as handle:
            handle.write('\nMONGO_SCHEMA_PASSWORD='+secrets.token_urlsafe(48)+'\n')
        path.chmod(0o600)
    print('Local schema secret is prepared; existing credentials preserved.')


if __name__=='__main__':prepare()
