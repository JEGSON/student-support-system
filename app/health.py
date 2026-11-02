"""Dependency health returns a boolean; never return topology or exceptions."""
import json
from urllib.request import urlopen
from flask import Blueprint, current_app, jsonify

health = Blueprint('health', __name__)


def database_ready():
    client = current_app.extensions['mongo']
    hello = client.admin.command('hello')
    # Stage 03 requires a writable replica set, not a standalone mock.
    if not hello.get('setName') or not hello.get('isWritablePrimary'):
        return False
    client[current_app.config['MONGODB_DATABASE']].command('ping')
    return True


def identity_ready():
    issuer = current_app.config['OIDC_ISSUER'].rstrip('/')
    with urlopen(issuer + '/.well-known/openid-configuration', timeout=2) as response:
        if response.status != 200:
            return False
        payload = response.read(65537)
        if len(payload) > 65536:
            return False
        document = json.loads(payload)
    if not isinstance(document, dict):
        return False
    methods = document.get('code_challenge_methods_supported')
    return (document.get('issuer') == issuer and isinstance(methods, list)
            and 'S256' in methods)


def email_ready():
    with urlopen(current_app.config['EMAIL_HEALTH_URL'], timeout=2) as response:
        return response.status == 200


@health.get('/health/live')
def live():
    return jsonify(status='alive')


@health.get('/health/ready')
def ready():
    healthy = True
    for check in current_app.extensions['readiness_checks']:
        try:
            if not check():
                healthy = False
        except Exception:
            # Details may include secrets; log a fixed event only.
            current_app.logger.warning('dependency_unavailable')
            healthy = False
    return jsonify(status='ready' if healthy else 'unavailable'), 200 if healthy else 503
