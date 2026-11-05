"""Host routing must never replay a form or route an unrecognised host."""

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

from app.portals import PortalHosts, create_portals


@pytest.fixture
def client():
    student = "http://127.0.0.1:5050"
    staff = "http://localhost:5050"
    gateway = PortalHosts(
        {
            "127.0.0.1:5050": Response("student"),
            "localhost:5050": Response("staff"),
        },
        student,
        staff,
    )
    return Client(gateway, Response)


def test_hosts_and_legacy_bookmarks(client):
    assert client.get("/", base_url="http://127.0.0.1:5050").text == "student"
    assert client.get("/", base_url="http://localhost:5050").text == "staff"
    assert client.get("/", base_url="http://other.invalid:5050").status_code == 400
    response = client.get("/university/account?next=/staff", base_url="http://127.0.0.1:5050")
    assert response.location == "http://localhost:5050/account?next=/staff"
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/student", base_url="http://localhost:5050").location == (
        "http://127.0.0.1:5050/"
    )
    assert client.get("/studentevil", base_url="http://localhost:5050").text == "staff"


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_legacy_mutations_require_a_new_form(client, method):
    response = client.open("/student/account", base_url="http://localhost:5050", method=method)
    assert response.status_code == 409
    assert "Location" not in response.headers


def test_distinct_ports_do_not_isolate_cookies(config):
    with pytest.raises(ValueError, match="distinct hostnames"):
        create_portals({**config, "STAFF_PORTAL_ORIGIN": "http://127.0.0.1:5001"})


@pytest.mark.parametrize("path", ["/staff/sign-in", "/staff", "/access/invitations", "/retention"])
def test_staff_bookmarks_on_student_host_use_staff_portal(client, path):
    response = client.get(path, base_url="http://127.0.0.1:5050")
    assert response.status_code == 302
    assert response.location == "http://localhost:5050" + path
    assert client.post(path, base_url="http://127.0.0.1:5050").status_code == 409


def test_student_case_links_on_staff_host_use_student_portal(client):
    response = client.get("/cases/new?category=finance", base_url="http://localhost:5050")
    assert response.location == "http://127.0.0.1:5050/cases/new?category=finance"
    assert client.post("/cases/new", base_url="http://localhost:5050").status_code == 409
