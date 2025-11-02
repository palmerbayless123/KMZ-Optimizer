"""Flask application factory."""

from __future__ import annotations

import logging
from flask import Flask
from flask_cors import CORS

from ..config import APP_CONFIG
from .routes import api_bp

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = APP_CONFIG.max_upload_bytes

    CORS(app)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    logger.info("Flask application initialised")
    return app
