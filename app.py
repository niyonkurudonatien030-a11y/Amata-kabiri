"""AmataShield Flask application factory."""
import os

from flask import Flask, jsonify, request, send_from_directory

from . import config, database
from .auth import ApiError
from .routes import bp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(test_config=None):
    app = Flask(__name__, static_folder=os.path.join(ROOT, "frontend"), static_url_path="")
    app.config.from_mapping(config.load())
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    database.init_app(app)
    database.ensure_schema(app.config["DATABASE"])
    app.register_blueprint(bp)

    @app.before_request
    def csrf_guard():
        # Browsers cannot add a custom header on cross-site form posts, so requiring it blocks CSRF.
        if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("X-Requested-With") != "AmataShield":
                return jsonify(error="Missing security header"), 403

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(self)")
        return resp

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify(error="File too large (maximum 8 MB)"), 413

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found"), 404
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    return app
