"""Separate, host-only student/staff entry points over one authorised case backend."""

from urllib.parse import urlsplit

from werkzeug.wrappers import Response


def create_portals(settings):
    from app import create_app

    student_origin = settings.get("STUDENT_PORTAL_ORIGIN", settings["APP_BASE_URL"]).rstrip("/")
    staff_origin = settings.get(
        "STAFF_PORTAL_ORIGIN", student_origin.replace("127.0.0.1", "localhost")
    ).rstrip("/")
    if urlsplit(student_origin).hostname == urlsplit(staff_origin).hostname:
        raise ValueError("Student and staff portals require distinct hostnames, not just ports.")
    apps = {}
    for kind, origin, other, client in [
        (
            "student",
            student_origin,
            staff_origin,
            settings.get("STUDENT_OIDC_CLIENT_ID", "support-student"),
        ),
        (
            "university",
            staff_origin,
            student_origin,
            settings.get("STAFF_OIDC_CLIENT_ID", "support-staff"),
        ),
    ]:
        app = create_app(
            {
                **settings,
                "APP_BASE_URL": origin,
                "PORTAL_KIND": kind,
                "OTHER_PORTAL_ORIGIN": other,
                "OIDC_CLIENT_ID": client,
                **(
                    {"SELF_REGISTRATION_ENABLED": "0", "ENROLMENT_MODE": "invitation"}
                    if kind == "university"
                    else {}
                ),
            }
        )
        apps[urlsplit(origin).netloc] = app
    return PortalHosts(apps, student_origin, staff_origin)


class PortalHosts:
    def __init__(self, apps, student_origin, staff_origin):
        self.apps = apps
        self.student_origin = student_origin
        self.staff_origin = staff_origin

    def __call__(self, environ, start_response):
        app = self.apps.get(environ.get("HTTP_HOST", ""))
        if not app:
            return Response("Unknown service address.", status=400)(environ, start_response)
        path = environ.get("PATH_INFO", "/")
        selected = None
        # Old pages may still link staff entry/actions on the student hostname.
        # Canonicalise navigation before loading a cookie from the wrong portal.
        for prefix, origin in [
            ("/staff", self.staff_origin),
            ("/access", self.staff_origin),
            ("/retention", self.staff_origin),
            ("/cases", self.student_origin),
        ]:
            if (path == prefix or path.startswith(prefix + "/")) and environ.get(
                "HTTP_HOST"
            ) != urlsplit(origin).netloc:
                selected = origin + path
                break
        # Retire the ambiguous path-only portals. Never forward an old POST.
        for prefix, origin in [
            ("/student", self.student_origin),
            ("/university", self.staff_origin),
        ]:
            if path == prefix or path.startswith(prefix + "/"):
                selected = origin + (path[len(prefix) :] or "/")
                break
        if selected:
            if environ.get("REQUEST_METHOD") not in {"GET", "HEAD"}:
                return Response(
                    "Open the portal and submit a new form.",
                    status=409,
                    headers={"Cache-Control": "no-store"},
                )(environ, start_response)
            query = environ.get("QUERY_STRING", "")
            return Response(
                status=302,
                headers={
                    "Location": selected + ("?" + query if query else ""),
                    "Cache-Control": "no-store",
                },
            )(environ, start_response)
        return app(environ, start_response)
