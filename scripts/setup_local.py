"""Generate local-only secrets without printing them; never overwrite existing setup."""
from pathlib import Path
import base64
import json
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def private_write(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        handle.write(content)


def main():
    if (ROOT / '.env').exists():
        raise SystemExit('Existing .env preserved. Use its matching local runtime files; no secrets changed.')
    runtime = ROOT / 'runtime'
    runtime.mkdir(exist_ok=True, mode=0o700)
    if any((runtime / name).exists() for name in ['mongo-keyfile', 'keycloak-import']):
        raise SystemExit('Existing runtime setup preserved. Resolve incomplete setup explicitly.')
    values = {key: secrets.token_urlsafe(48) for key in
              ['MONGO_ROOT_PASSWORD', 'MONGO_APP_PASSWORD', 'MONGO_TEST_PASSWORD', 'MONGO_SCHEMA_PASSWORD', 'OIDC_ADMIN_PASSWORD']}
    app_uri = f"mongodb://support_app:{values['MONGO_APP_PASSWORD']}@localhost:27017/admin?replicaSet=rs0&directConnection=true"
    config = {
        'APP_ENV':'development', 'FLASK_DEBUG':'0', 'APP_BASE_URL':'http://127.0.0.1:5050',
        'SECRET_KEY':'dev-' + secrets.token_urlsafe(64), 'MONGODB_URI':app_uri,
        'MONGODB_DATABASE':'student_support_dev',
        'OIDC_ISSUER':'http://127.0.0.1:8180/realms/student-support',
        'OIDC_CLIENT_ID':'support-local', 'EMAIL_HEALTH_URL':'http://127.0.0.1:8025/readyz',
        **values,
    }
    realm = {'realm':'student-support','enabled':True,'displayName':'Synthetic Student Support',
             'registrationAllowed':False,'resetPasswordAllowed':False,'sslRequired':'none',
             'clients':[{'clientId':'support-local','enabled':True,'publicClient':True,
                         'standardFlowEnabled':True,'directAccessGrantsEnabled':False,
                         'redirectUris':['http://127.0.0.1:5050/auth/callback'],
                         'attributes':{'pkce.code.challenge.method':'S256'}}]}
    private_write(runtime/'mongo-keyfile', base64.b64encode(secrets.token_bytes(512)).decode('ascii'))
    # Realm contains no secrets; readable by the non-root identity container.
    realm_dir = runtime/'keycloak-import'
    realm_dir.mkdir(mode=0o755)
    (realm_dir/'student-support-realm.json').write_text(json.dumps(realm, indent=2))
    (realm_dir/'student-support-realm.json').chmod(0o644)
    private_write(ROOT/'.env', ''.join(f'{k}={v}\n' for k,v in config.items()))
    print('Generated ignored local configuration and keyfile. Secret values were not printed.')


if __name__ == '__main__':
    main()
