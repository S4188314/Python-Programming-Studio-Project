from sqlite3 import DatabaseError

from flask import Blueprint, flash, render_template, request, url_for

from db_queries import get_all_diseases, get_all_years, get_countries_above_global_average


above_avg_bp = Blueprint("above_avg", __name__)


@above_avg_bp.route("/above-average-infection")
def above_average_infection():
    diseases = get_all_diseases()
    years = get_all_years()
    selected = _validated_filters(diseases, years)
    rows, global_rate = _query_results(selected)

    return render_template(
        "above_average.html",
        active_page="above_avg",
        diseases=diseases,
        years=years,
        selected=selected,
        active_filters=_active_filters(selected),
        rows=rows,
        global_rate=global_rate,
        results_count=max(len(rows) - 1, 0),
        reset_url=url_for("above_avg.above_average_infection"),
        submitted=bool(request.args),
    )


def _validated_filters(diseases, years):
    return {
        "disease": _choice("disease", {item["code"] for item in diseases}),
        "year": _choice("year", {str(year) for year in years}),
    }


def _choice(name, allowed):
    value = request.args.get(name, "")
    if value and value not in allowed:
        flash(f"Ignored an invalid {name} filter.", "warning")
        return ""
    return value


def _query_results(selected):
    if selected["disease"] and selected["year"]:
        try:
            return get_countries_above_global_average(selected["disease"], selected["year"])
        except DatabaseError:
            flash("Database error. Please try again.", "error")
            return [], None

    if request.args:
        flash("Select an infection type and year to analyse global averages.", "info")
    return [], None


def _active_filters(selected):
    labels = {"disease": "Infection", "year": "Year"}
    return {labels[key]: value for key, value in selected.items() if value}
