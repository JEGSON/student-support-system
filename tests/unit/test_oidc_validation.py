import time

import pytest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey

from app.auth.routes import safe_return_path


@pytest.mark.parametrize(
    "value",
    [
        "//evil.invalid",
        "https://evil.invalid",
        "/%2f%2fevil.invalid",
        "/account?next=evil",
        "/account#x",
        "/\\evil",
        "http://[",
        "/account\n",
        "/cases/1",
        None,
    ],
)
def test_return_path_allowlist(value):
    assert safe_return_path(value) == "/account"


def test_safe_return():
    assert safe_return_path("/access") == "/access"


@pytest.mark.parametrize(
    "defect",
    ["issuer", "audience", "nonce", "expired", "signature", "algorithm", "missing_sub", "valid"],
)
def test_real_signed_id_token_validation(app, monkeypatch, defect):
    key = RSAKey.generate_key(2048, parameters={"kid": "primary"})
    wrong = RSAKey.generate_key(2048, parameters={"kid": "primary"})
    client = app.extensions["university_oidc"]
    now = int(time.time())
    claims = {
        "iss": app.config["OIDC_ISSUER"],
        "aud": "support-test",
        "sub": "synthetic",
        "iat": now,
        "exp": now + 300,
        "nonce": "expected",
    }
    if defect == "issuer":
        claims["iss"] = "https://attacker.invalid"
    if defect == "audience":
        claims["aud"] = "other"
    if defect == "nonce":
        claims["nonce"] = "wrong"
    if defect == "expired":
        claims["exp"] = now - 100
    if defect == "missing_sub":
        claims.pop("sub")
    token = jwt.encode(
        {"alg": "RS512" if defect == "algorithm" else "RS256", "kid": "primary"},
        claims,
        wrong if defect == "signature" else key,
        algorithms=["RS256", "RS512"],
    )
    metadata = {
        "issuer": app.config["OIDC_ISSUER"],
        "code_challenge_methods_supported": ["S256"],
        "id_token_signing_alg_values_supported": ["RS256"],
        **{
            name: app.config["OIDC_ISSUER"] + "/" + name
            for name in ("authorization_endpoint", "token_endpoint", "jwks_uri")
        },
    }
    monkeypatch.setattr(client, "load_server_metadata", lambda: metadata)
    monkeypatch.setattr(
        client, "fetch_jwk_set", lambda **kw: {"keys": [key.as_dict(private=False)]}
    )
    with app.test_request_context("/"):
        if defect == "valid":
            assert (
                client.parse_id_token({"id_token": token}, nonce="expected", leeway=0)["sub"]
                == "synthetic"
            )
        else:
            with pytest.raises(JoseError):
                client.parse_id_token({"id_token": token}, nonce="expected", leeway=0)


def test_wrong_state_never_exchanges_code(app, monkeypatch):
    client = app.extensions["university_oidc"]

    called = []

    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("No token exchange permitted.")

    monkeypatch.setattr(client, "fetch_access_token", forbidden)
    assert app.test_client().get("/auth/callback?state=forged&code=forged").status_code == 400
    assert called == []


def test_request_log_has_no_callback_query():
    from scripts.run_local import SafeRequestHandler

    handler = object.__new__(SafeRequestHandler)
    handler.command = "GET"
    handler.requestline = "GET /auth/callback?code=secret&state=private HTTP/1.1"
    output = []
    handler.log = lambda *args: output.append(args)
    handler.log_request(302)
    assert "secret" not in str(output) and "private" not in str(output)


@pytest.mark.parametrize(
    "defect", ["issuer", "cross_origin_endpoint", "missing_pkce", "wrong_algorithm"]
)
def test_discovery_is_pinned_to_configured_issuer_and_endpoints(app, monkeypatch, defect):
    from authlib.integrations.flask_client.apps import FlaskOAuth2App

    from app.auth.oidc import IdentityConfigurationError

    issuer = app.config["OIDC_ISSUER"]
    metadata = {
        "issuer": issuer,
        "code_challenge_methods_supported": ["S256"],
        "id_token_signing_alg_values_supported": ["RS256"],
        **{k: issuer + "/" + k for k in ("authorization_endpoint", "token_endpoint", "jwks_uri")},
    }
    if defect == "issuer":
        metadata["issuer"] = "http://127.0.0.1:8080/other"
    if defect == "cross_origin_endpoint":
        metadata["token_endpoint"] = "https://attacker.invalid/token"
    if defect == "missing_pkce":
        metadata["code_challenge_methods_supported"] = ["plain"]
    if defect == "wrong_algorithm":
        metadata["id_token_signing_alg_values_supported"] = ["HS256"]
    monkeypatch.setattr(FlaskOAuth2App, "load_server_metadata", lambda self: metadata)
    with app.app_context(), pytest.raises(IdentityConfigurationError):
        app.extensions["university_oidc"].load_server_metadata()
