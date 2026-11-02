import pytest

from app import create_app
from app.config import ConfigurationError
from app.services.accounts import LOCAL_ISSUER, profile_errors


@pytest.mark.parametrize("value", ["", "  ", "x" * 161, "Name\nRole", "Name\x00", "Name\x7f", {}])
def test_profile_rejects_invalid_name(value):
    assert "display_name" in profile_errors({"display_name": value, "course_label": ""})


def test_profile_allows_unicode_optional_course_and_plain_text():
    assert not profile_errors({"display_name": " Zoë <student> ", "course_label": ""})
    assert "course_label" in profile_errors({"display_name": "Demo", "course_label": "x" * 161})


@pytest.mark.parametrize("flag", ["true", "yes", "2"])
def test_registration_flag_is_explicit(config, flag):
    with pytest.raises(ConfigurationError):
        create_app({**config, "SELF_REGISTRATION_ENABLED": flag})


def test_registration_only_uses_local_synthetic_provider(config):
    with pytest.raises(ConfigurationError, match="synthetic"):
        create_app({**config, "SELF_REGISTRATION_ENABLED": "1"})
    app = create_app({**config, "SELF_REGISTRATION_ENABLED": "1", "OIDC_ISSUER": LOCAL_ISSUER})
    assert app.config["SELF_REGISTRATION_ENABLED"]
    app.extensions["mongo"].close()
