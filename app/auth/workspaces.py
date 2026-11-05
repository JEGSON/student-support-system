"""Fixed account workspaces: cookie isolation, never a permission or role grant."""

from flask import current_app, request, url_for

WORKSPACES = {"student": "/student", "university": "/university"}


class AccountWorkspaces:
    def __init__(self, application, portal="general"):
        self.app = application
        self.portal = portal

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        environ["support.workspace"] = self.portal
        if self.portal != "general":
            return self.app(environ, start_response)
        for name, prefix in WORKSPACES.items():
            if path == prefix or path.startswith(prefix + "/"):
                environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + prefix
                environ["PATH_INFO"] = path[len(prefix) :] or "/"
                environ["support.workspace"] = name
                break
        return self.app(environ, start_response)


def workspace():
    return request.environ.get("support.workspace", "general")


def cookie_settings():
    name = workspace()
    return (
        "support_session" + ("_" + name if name in WORKSPACES else ""),
        "/" if current_app.config["PORTAL_KIND"] != "general" else WORKSPACES.get(name, "/"),
    )


def workspace_url(endpoint, name):
    if current_app.config["PORTAL_KIND"] != "general":
        return (
            ""
            if name == current_app.config["PORTAL_KIND"]
            else current_app.config["OTHER_PORTAL_ORIGIN"]
        ) + url_for(endpoint)
    prefix = WORKSPACES[name]
    path = url_for(endpoint)
    root = request.script_root
    if root:
        path = path[len(root) :]
    return prefix + path


def callback_url():
    return current_app.config["APP_BASE_URL"].rstrip("/") + url_for("identity.callback")
