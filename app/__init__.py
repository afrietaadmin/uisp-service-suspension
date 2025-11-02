from flask import Flask
from app.blueprints.suspensions import suspend_unsuspend_blueprint


def create_app():
    """Factory method to create Flask app."""
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(suspend_unsuspend_blueprint, url_prefix="/service_suspensions")

    # Healthcheck endpoint
    @app.route("/healthz", methods=["GET"])
    def healthz():
        return {"status": "ok"}, 200

    return app


# Allow running via python -m flask or gunicorn
app = create_app()
