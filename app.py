"""Entry point for the KMZ Optimizer Flask application."""

from __future__ import annotations

from kmz_optimizer import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
