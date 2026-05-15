from sqlite3 import DatabaseError

from flask import Blueprint, flash, redirect, render_template, request, url_for

from db_queries import get_all_antigens, get_all_years, get_top_improving_countries, get_year_range


improvement_bp = Blueprint("improvement", __name__)


@improvement_bp.route("/vaccination-improvement")
def vaccination_improvement():
    antigens = get_all_antigens()
    years = get_all_years()
    selected = _validated_filters(antigens, years)
    redirect_target = _validation_redirect(selected)

    if redirect_target:
        return redirect_target

    rows = _query_results(selected)
    return render_template(
        "vax_improvement.html",
        active_page="improvement",
        antigens=antigens,
        years=years,
        year_range=get_year_range(),
        selected=selected,
        active_filters=_active_filters(selected),
        rows=rows,
        results_count=len(rows),
        reset_url=url_for("improvement.vaccination_improvement"),
        submitted=bool(request.args),
    )


def _validated_filters(antigens, years):
    antigen_codes = {item["code"] for item in antigens}
    year_values = {str(year) for year in years}
    return {
        "antigen": _choice("antigen", antigen_codes),
        "start_year": _choice("start", year_values),
        "end_year": _choice("end", year_values),
        "top_n": _top_n(),
    }


def _choice(name, allowed):
    value = request.args.get(name, "")
    if value and value not in allowed:
        flash(f"Ignored an invalid {name} filter.", "warning")
        return ""
    return value


def _top_n():
    try:
        top_n = int(request.args.get("top", "10"))
    except ValueError:
        flash("Top N must be a whole number.", "warning")
        return 10
    return min(max(top_n, 1), 50)


def _validation_redirect(selected):
    if selected["start_year"] and selected["end_year"] and int(selected["start_year"]) >= int(selected["end_year"]):
        flash("Start year must be earlier than end year.", "warning")
        return redirect(url_for("improvement.vaccination_improvement"))
    return None


def _query_results(selected):
    rows = []
    if selected["antigen"] and selected["start_year"] and selected["end_year"]:
        try:
            rows = get_top_improving_countries(
                selected["antigen"],
                selected["start_year"],
                selected["end_year"],
                selected["top_n"],
            )
        except DatabaseError:
            flash("Database error. Please try again.", "error")
    elif request.args:
        flash("Select start year, end year, and antigen to analyse improvements.", "info")
    return rows


def _active_filters(selected):
    filters = {}
    if selected["antigen"]:
        filters["Antigen"] = selected["antigen"]
    if selected["start_year"]:
        filters["Start Year"] = selected["start_year"]
    if selected["end_year"]:
        filters["End Year"] = selected["end_year"]
    if request.args.get("top"):
        filters["Top N"] = selected["top_n"]
    return filters
