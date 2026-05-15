from sqlite3 import DatabaseError

from flask import Blueprint, flash, render_template

from db_queries import get_personas, get_team_members


mission_bp = Blueprint("mission", __name__)


@mission_bp.route("/mission")
def mission():
    try:
        personas = get_personas()
        team_members = get_team_members()
    except DatabaseError:
        flash("Database error. Please try again.", "error")
        personas, team_members = [], []

    return render_template(
        "mission.html",
        active_page="mission",
        personas=personas,
        team_members=team_members,
        results_count=len(personas) + len(team_members),
    )
