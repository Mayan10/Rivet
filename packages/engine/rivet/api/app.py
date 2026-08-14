"""Flask application factory."""

from __future__ import annotations

import pathlib

from flask import Flask, render_template


def _find_web_dir() -> pathlib.Path:
    """Locate the top-level ``web/`` directory (templates + static assets).

    The web UI lives outside the installable package (it's a thin client
    over the API, not a library consumers import), so it's only available
    when running from a source checkout -- documented in the README.
    """
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "web"
        if candidate.is_dir():
            return candidate
    raise RuntimeError(
        "Could not locate the 'web/' directory (UI templates/static). "
        "Run Rivet's web server from a source checkout, e.g. "
        "`python scripts/run_dev_server.py` from the repo root."
    )


def create_app(output_dir: str | None = None) -> Flask:
    web_dir = _find_web_dir()
    app = Flask(
        __name__,
        template_folder=str(web_dir / "templates"),
        static_folder=str(web_dir / "static"),
    )
    app.config["RIVET_OUTPUT_DIR"] = output_dir or str(pathlib.Path.cwd() / ".rivet_outputs")

    from .routes import api_bp, download_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(download_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app


def main() -> None:
    create_app().run(debug=True, port=5000)


if __name__ == "__main__":
    main()
