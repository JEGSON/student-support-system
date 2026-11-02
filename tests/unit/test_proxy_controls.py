import pytest

from app import create_app
from app.config import ConfigurationError


def test_untrusted_forwarded_headers_rejected(app):
    for headers in [
        {"X-Forwarded-For": "1.2.3.4"},
        {"X-Forwarded-Proto": "https"},
        {"Forwarded": "for=1.2.3.4;proto=https"},
    ]:
        assert app.test_client().get("/", headers=headers).status_code == 400


def test_exact_single_proxy_hop(config):
    app = create_app(
        {**config, "TRUST_PROXY": "1", "PROXY_HOPS": "1", "PROXY_TRUSTED_IP": "127.0.0.1"}
    )
    client = app.test_client()
    headers = {"X-Forwarded-For": "192.0.2.10", "X-Forwarded-Proto": "https"}
    assert client.get("/", headers=headers).status_code == 200
    assert (
        client.get("/", headers={**headers, "X-Forwarded-Host": "evil.invalid"}).status_code == 400
    )
    assert (
        client.get(
            "/", headers={**headers, "X-Forwarded-For": "192.0.2.10, 192.0.2.11"}
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/", headers=headers, environ_overrides={"REMOTE_ADDR": "192.0.2.20"}
        ).status_code
        == 400
    )
    assert client.get("/").status_code == 400
    app.extensions["mongo"].close()


@pytest.mark.parametrize(
    "settings",
    [
        {"TRUST_PROXY": "1", "PROXY_HOPS": "2"},
        {"TRUST_PROXY": "yes"},
        {"RATE_LIMIT_READ": "0"},
        {"RATE_LIMIT_WRITE": "10001"},
    ],
)
def test_operational_misconfiguration_fails(config, settings):
    with pytest.raises(ConfigurationError):
        create_app({**config, **settings})
