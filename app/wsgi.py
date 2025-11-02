"""
WSGI entrypoint for Gunicorn.
"""

import logging

try:
    from app import create_app
except Exception as e:
    raise RuntimeError("Failed to import Flask app from app.__init__.py") from e

app = create_app()

logging.basicConfig(level=logging.INFO)
logging.getLogger(__name__).info("WSGI application loaded successfully.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
