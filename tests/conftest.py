import secrets
import pytest
from app import create_app


@pytest.fixture
def config():
    return dict(APP_ENV='testing', SECRET_KEY=secrets.token_urlsafe(64),
                FLASK_DEBUG='0', APP_BASE_URL='http://127.0.0.1:5000',
                MONGODB_URI='mongodb://localhost:27017/?replicaSet=rs0',
                MONGODB_DATABASE='student_support_test',
                OIDC_ISSUER='http://127.0.0.1:8080/realms/student-support',
                EMAIL_HEALTH_URL='http://127.0.0.1:8025/readyz')


@pytest.fixture
def app(config):
    application = create_app(config)
    yield application
    application.extensions['mongo'].close()
