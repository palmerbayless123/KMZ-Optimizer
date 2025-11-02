"""Flask application factory."""

from __future__ import annotations

import logging
from flask import Flask
from flask_cors import CORS
from redis import Redis
from rq import Queue

from ..config import APP_CONFIG, QUEUE_CONFIG
from .routes import api_bp

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = APP_CONFIG.max_upload_bytes

    CORS(app)
    app.register_blueprint(api_bp, url_prefix="/api")

    redis_connection = Redis.from_url(QUEUE_CONFIG.redis_url)
    queue = Queue(
        name=QUEUE_CONFIG.queue_name,
        connection=redis_connection,
        default_timeout=QUEUE_CONFIG.default_timeout,
    )
    app.extensions["rq"] = {"queue": queue, "connection": redis_connection}

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    logger.info("Flask application initialised")
    return app
