# app.py
# Purpose: create the Flask app and register all routes.

from flask import Flask

from routes.above_avg import above_avg_bp
from routes.improvement import improvement_bp
from routes.infection import infection_bp
from routes.landing import landing_bp
from routes.mission import mission_bp
from routes.vax_rates import vax_rates_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = "vaxtrack-secret-key"

    app.register_blueprint(landing_bp)
    app.register_blueprint(mission_bp)
    app.register_blueprint(vax_rates_bp)
    app.register_blueprint(infection_bp)
    app.register_blueprint(improvement_bp)
    app.register_blueprint(above_avg_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
