from sqlite3 import DatabaseError

from flask import Blueprint, flash, render_template

from db_queries import get_disease_list, get_landing_stats


landing_bp = Blueprint("landing", __name__)


@landing_bp.route("/")
@landing_bp.route("/index")
def index():
    try:
        stats = get_landing_stats()
        diseases = get_disease_list()
    except DatabaseError:
        flash("Database error. Please try again.", "error")
        stats, diseases = {}, []

    return render_template(
        "index.html",
        active_page="home",
        stats=stats,
        diseases=diseases,
        results_count=len(diseases),
    )
