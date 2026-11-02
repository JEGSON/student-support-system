import secrets
import pytest
from app import create_app
from app.config import ConfigurationError, load_config


def test_missing_and_placeholder_secret_rejected(config):
    for secret in ['', 'REPLACE_WITH_GENERATED_LOCAL_SECRET', 'short']:
        with pytest.raises(ConfigurationError):
            create_app({**config, 'SECRET_KEY': secret})


@pytest.mark.parametrize('env,database', [('testing','student_support_dev'),('development','student_support_test')])
def test_database_isolation(config, env, database):
    with pytest.raises(ConfigurationError, match='isolated'):
        create_app({**config,'APP_ENV':env,'MONGODB_DATABASE':database})


def production_config(config):
    return {**config,'APP_ENV':'production','APP_BASE_URL':'https://support.example.invalid',
            'MONGODB_URI':'mongodb://localhost:27017/?tls=true',
            'MONGODB_DATABASE':'student_support_production',
            'OIDC_ISSUER':'https://identity.example.invalid/realm',
            'EMAIL_HEALTH_URL':'https://mail.example.invalid/ready'}


def test_production_refuses_development_config(config):
    with pytest.raises(ConfigurationError):
        create_app({**config,'APP_ENV':'production'})
    with pytest.raises(ConfigurationError):
        create_app({**production_config(config),'SECRET_KEY':'dev-'+secrets.token_urlsafe(64)})
    with pytest.raises(ConfigurationError):
        create_app({**production_config(config),'MONGODB_URI':'mongodb://localhost:27017/'})


def test_debugger_is_forbidden(config):
    with pytest.raises(ConfigurationError):
        create_app({**config,'FLASK_DEBUG':'1'})


def test_public_and_errors_do_not_expose_config(app):
    client=app.test_client()
    for path, status in [('/',200),('/sign-in',503),('/cases/demo',404),('/admin',404)]:
        response=client.get(path)
        assert response.status_code==status
        assert app.config['SECRET_KEY'].encode() not in response.data
        assert b'mongodb://' not in response.data
        assert 'no-store' in response.headers['Cache-Control']
        assert "script-src 'none'" in response.headers['Content-Security-Policy']
        assert response.headers['X-Content-Type-Options']=='nosniff'
    assert client.post('/').status_code==405
    assert client.get('/',headers={'Host':'evil.example'}).status_code==400
    assert not client.get('/').headers.get('Set-Cookie')


def test_readiness_fails_closed_and_checks_all_dependencies(app, caplog):
    visited=[]
    def failure():
        visited.append('database')
        raise RuntimeError('sensitive-connection-string')
    def okay():
        visited.append('identity')
        return True
    app.extensions['readiness_checks']=[failure,okay,lambda:False]
    response=app.test_client().get('/health/ready')
    assert response.status_code==503 and response.json=={'status':'unavailable'}
    assert visited==['database','identity']
    assert 'sensitive-connection-string' not in caplog.text
    app.extensions['readiness_checks']=[lambda:True]*3
    assert app.test_client().get('/health/ready').json=={'status':'ready'}
    assert app.test_client().get('/health/live').json=={'status':'alive'}


def test_gallery_excluded_from_test_and_production(config):
    for values in [config,production_config(config)]:
        application=create_app(values)
        assert not any(rule.rule.startswith('/_dev') for rule in application.url_map.iter_rules())
        assert application.test_client().get('/_dev/components', base_url=values['APP_BASE_URL']).status_code==404
        application.extensions['mongo'].close()


def test_gallery_is_development_only_synthetic_and_escaped(config):
    application=create_app({**config,'APP_ENV':'development','MONGODB_DATABASE':'student_support_dev'})
    client=application.test_client()
    for path in ['/components','/shell/student','/shell/staff']:
        response=client.get('/_dev'+path)
        assert response.status_code==200 and b'synthetic' in response.data.lower()
        assert b'style=' not in response.data
    with application.app_context():
        template=application.jinja_env.from_string("{% from 'components/ui.html' import alert %}{{ alert(value,value) }}")
        html=template.render(value='<script>alert(1)</script>')
        assert '<script>' not in html and '&lt;script&gt;' in html
    assert client.get('/cases/SS-DEMO-001').status_code==404
    application.extensions['mongo'].close()


def test_unexpected_error_hides_exception_in_response_and_logs(config, caplog):
    application=create_app(config)
    application.config['PROPAGATE_EXCEPTIONS']=False
    @application.get('/synthetic-error')
    def explode():
        raise RuntimeError('synthetic-sensitive-marker')
    response=application.test_client().get('/synthetic-error')
    assert response.status_code==500
    assert b'synthetic-sensitive-marker' not in response.data
    assert 'synthetic-sensitive-marker' not in caplog.text
    application.extensions['mongo'].close()


@pytest.mark.parametrize('option', ['tls=false','tls=true&tlsAllowInvalidCertificates=true','tls=true&tlsInsecure=true','tls=true&tlsAllowInvalidHostnames=true','tls=true&tls=false'])
def test_production_disallows_insecure_database_options(config, option):
    with pytest.raises(ConfigurationError):
        create_app({**production_config(config),'MONGODB_URI':'mongodb://localhost:27017/?'+option})


def test_body_limit_and_absent_client_session_fallback(config):
    from flask import request, session
    application=create_app(config)
    application.config['PROPAGATE_EXCEPTIONS']=False
    @application.post('/body-probe')
    def body_probe():
        return str(len(request.get_data()))
    @application.get('/session-probe')
    def session_probe():
        session['user_id']='synthetic'
        return 'should not save'
    client=application.test_client()
    assert client.post('/body-probe',data=b'x'*65537).status_code==413
    response=client.get('/session-probe')
    assert response.status_code==500 and 'Set-Cookie' not in response.headers
    application.extensions['mongo'].close()
