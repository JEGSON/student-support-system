"""WSGI entry point; production environment must be supplied externally."""
from app import create_app
application = create_app()
