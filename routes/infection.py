from sqlite3 import DatabaseError

from flask import Blueprint, flash, render_template, request, url_for

from db_queries import get_all_diseases, get_all_economies, get_all_years
from db_queries import get_infection_anomaly_count, get_infection_by_country
from db_queries import get_infection_summary_by_economy, get_infection_summary_cards


infection_bp = Blueprint("infection", __name__)
SORTS = {"disease", "country", "economic_phase", "year", "cases_per_100k", "total_cases"}
ORDERS = {"asc", "desc"}
VIEWS = {"country", "summary"}


@infection_bp.route("/infection-by-economy")
def infection_by_economy():
    options = _load_options()
    selected = _validated_filters(options)
    sort = request.args.get("sort", "cases_per_100k")
    order = request.args.get("order", "desc")
    sort = sort if sort in SORTS else "cases_per_100k"
    order = order if order in ORDERS else "desc"

    context = _build_context(options, selected, sort, order)
    return render_template("infection_economy.html", **context)


def _load_options():
    return {
        "economies": get_all_economies(),
        "diseases": get_all_diseases(),
        "years": get_all_years(),
    }


def _validated_filters(options):
    return {
        "status": _choice("status", set(options["economies"])),
        "disease": _choice("disease", {item["code"] for item in options["diseases"]}),
        "year": _choice("year", {str(year) for year in options["years"]}),
        "view": _choice("view", VIEWS) or "country",
    }


def _choice(name, allowed):
    value = request.args.get(name, "")
    if value and value not in allowed:
        flash(f"Ignored an invalid {name} filter.", "warning")
        return ""
    return value


def _build_context(options, selected, sort, order):
    country_rows, summary_rows, cards = [], [], []
    if selected["status"] and selected["disease"] and selected["year"]:
        try:
            country_rows = get_infection_by_country(selected["status"], selected["disease"], selected["year"], sort, order)
            summary_rows = get_infection_summary_by_economy(selected["status"], selected["disease"], selected["year"], sort, order)
            cards = get_infection_summary_cards(selected["status"], selected["disease"], selected["year"])
        except DatabaseError:
            flash("Database error. Please try again.", "error")
    else:
        flash("Select an economic status, infection type, and year to view results.", "info")

    visible_count = len(country_rows) if selected["view"] == "country" else len(summary_rows)
    return {
        "active_page": "infection",
        "economies": options["economies"],
        "diseases": options["diseases"],
        "years": options["years"],
        "selected": selected,
        "active_filters": _active_filters(selected),
        "country_rows": country_rows,
        "summary_rows": summary_rows,
        "summary_cards": cards,
        "sort": sort,
        "order": order,
        "sort_urls": _sort_urls(selected, sort, order),
        "sort_marks": _sort_marks(sort, order),
        "results_count": visible_count,
        "anomaly_count": get_infection_anomaly_count(),
        "reset_url": url_for("infection.infection_by_economy"),
    }


def _active_filters(selected):
    labels = {"status": "Economic Status", "disease": "Infection", "year": "Year"}
    return {labels[key]: value for key, value in selected.items() if key in labels and value}


def _sort_urls(selected, sort, order):
    params = {key: value for key, value in selected.items() if value}
    return {
        column: url_for(
            "infection.infection_by_economy",
            **params,
            sort=column,
            order=_next_order(column, sort, order),
        )
        for column in SORTS
    }


def _sort_marks(sort, order):
    return {column: ("up" if sort == column and order == "asc" else "down" if sort == column else "") for column in SORTS}


def _next_order(column, sort, order):
    return "desc" if sort == column and order == "asc" else "asc"
