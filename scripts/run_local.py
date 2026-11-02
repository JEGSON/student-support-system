"""Explicit loopback-only development runner; debugger cannot be enabled."""
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from app import create_app

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
app = create_app()
if app.config['APP_ENV'] != 'development':
    raise SystemExit('This runner is restricted to local development.')
app.run(host='127.0.0.1', port=urlsplit(app.config['APP_BASE_URL']).port or 5050, debug=False, use_reloader=False)
