"""Entry point for the KMZ Optimizer Flask application."""

from __future__ import annotations

import os

from kmz_optimizer import create_app

app = create_app()


def _is_production() -> bool:
    """Return ``True`` when the app should run in production mode."""

    return os.environ.get("FLASK_ENV", "production") == "production"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = not _is_production()
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=debug)
