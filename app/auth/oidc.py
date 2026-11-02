"""Maintained Authlib OIDC integration, pinned issuer/origins/signing algorithm."""

from urllib.parse import urlsplit

from authlib.integrations.flask_client import OAuth
from authlib.integrations.flask_client.apps import FlaskOAuth2App
from flask import current_app


class IdentityConfigurationError(ValueError):
    pass


class UniversityOIDC(FlaskOAuth2App):
    def load_server_metadata(self):
        metadata = super().load_server_metadata()
        issuer = current_app.config["OIDC_ISSUER"].rstrip("/")
        origin = urlsplit(issuer)
        if metadata.get("issuer") != issuer or "S256" not in metadata.get(
            "code_challenge_methods_supported", []
        ):
            raise IdentityConfigurationError("Identity configuration could not be validated.")
        for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            endpoint = urlsplit(metadata.get(name, ""))
            if (
                endpoint.scheme != origin.scheme
                or endpoint.netloc != origin.netloc
                or endpoint.username
                or endpoint.fragment
            ):
                raise IdentityConfigurationError("Identity endpoint could not be validated.")
        if "RS256" not in metadata.get("id_token_signing_alg_values_supported", []):
            raise IdentityConfigurationError("Required identity signature is unavailable.")
        # The token's own algorithm/header never broadens the configured allowlist.
        metadata["id_token_signing_alg_values_supported"] = ["RS256"]
        return metadata


def configure_oidc(app):
    oauth = OAuth(app)
    oauth.register(
        "university",
        client_cls=UniversityOIDC,
        client_id=app.config["OIDC_CLIENT_ID"],
        client_secret=app.config.get("OIDC_CLIENT_SECRET"),
        server_metadata_url=app.config["OIDC_ISSUER"].rstrip("/")
        + "/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile",
            "code_challenge_method": "S256",
            "token_endpoint_auth_method": app.config["OIDC_TOKEN_AUTH_METHOD"],
            "default_timeout": 5,
        },
    )
    app.extensions["university_oidc"] = oauth.create_client("university")
