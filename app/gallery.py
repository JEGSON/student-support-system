"""Development-only synthetic design gallery, never registered in test/production."""

from flask import Blueprint, abort, render_template

gallery = Blueprint("gallery", __name__, url_prefix="/_dev")


@gallery.get("/components")
def components():
    return render_template(
        "gallery/states.html", title="Component gallery", context="public", development_preview=True
    )


@gallery.get("/shell/<context>")
def shell(context):
    if context not in {"student", "staff"}:
        abort(404)
    return render_template(
        f"gallery/{context}.html",
        title=f"{context.title()} shell",
        context=context,
        development_preview=True,
    )
