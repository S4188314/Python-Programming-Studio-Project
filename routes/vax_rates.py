import csv
import io
from sqlite3 import DatabaseError

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from db_queries import get_all_antigens, get_all_countries, get_all_regions, get_all_years
from db_queries import get_countries_meeting_target, get_regions_summary
from db_queries import get_vaccination_anomaly_count


vax_rates_bp = Blueprint("vax_rates", __name__)
SORTS = {"antigen", "year", "country", "region", "pct_of_target"}
ORDERS = {"asc", "desc"}


@vax_rates_bp.route("/vaccination-rates")
def vaccination_rates():
    options = _load_options()
    selected = _validated_filters(options)
    sort = request.args.get("sort", "pct_of_target")
    order = request.args.get("order", "desc")
    sort = sort if sort in SORTS else "pct_of_target"
    order = order if order in ORDERS else "desc"

    if request.args.get("download"):
        return _download(selected, sort, order)

    context = _build_context(options, selected, sort, order)
    return render_template("vaccination_rates.html", **context)


def _load_options():
    return {
        "antigens": get_all_antigens(),
        "years": get_all_years(),
        "regions": get_all_regions(),
        "countries": get_all_countries(),
    }


def _validated_filters(options):
    antigen_codes = {item["code"] for item in options["antigens"]}
    country_codes = {item["code"] for item in options["countries"]}
    years = {str(year) for year in options["years"]}
    regions = set(options["regions"])

    return {
        "antigen": _choice("antigen", antigen_codes),
        "year": _choice("year", years),
        "region": _choice("region", regions),
        "country": _choice("country", country_codes),
    }


def _choice(name, allowed):
    value = request.args.get(name, "")
    if value and value not in allowed:
        flash(f"Ignored an invalid {name} filter.", "warning")
        return ""
    return value


def _build_context(options, selected, sort, order):
    table1, table2 = [], []
    active_filters = _active_filters(selected)

    if selected["antigen"] and selected["year"]:
        try:
            table1 = get_countries_meeting_target(**selected, sort_col=sort, order=order)
            table2 = get_regions_summary(**selected, sort_col="countries_met", order="desc")
        except DatabaseError:
            flash("Database error. Please try again.", "error")
    else:
        flash("Please select both an antigen and a year to view results.", "info")

    return {
        "active_page": "vax_rates",
        "antigens": options["antigens"],
        "years": options["years"],
        "regions": options["regions"],
        "countries": options["countries"],
        "selected": selected,
        "active_filters": active_filters,
        "table1": table1,
        "table2": table2,
        "sort": sort,
        "order": order,
        "sort_urls": _sort_urls(selected, sort, order),
        "sort_marks": _sort_marks(sort, order),
        "download_urls": _download_urls(selected, sort, order),
        "results_count": len(table1),
        "anomaly_count": get_vaccination_anomaly_count(),
        "reset_url": url_for("vax_rates.vaccination_rates"),
    }


def _active_filters(selected):
    labels = {"antigen": "Antigen", "year": "Year", "region": "Region", "country": "Country"}
    return {labels[key]: value for key, value in selected.items() if value}


def _sort_urls(selected, sort, order):
    params = {key: value for key, value in selected.items() if value}
    return {
        column: url_for(
            "vax_rates.vaccination_rates",
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


def _download_urls(selected, sort, order):
    if not selected["antigen"] or not selected["year"]:
        return {}
    params = {key: value for key, value in selected.items() if value}
    return {
        "countries": url_for("vax_rates.vaccination_rates", **params, sort=sort, order=order, download="countries"),
        "regions": url_for("vax_rates.vaccination_rates", **params, sort=sort, order=order, download="regions"),
    }


def _download(selected, sort, order):
    if not selected["antigen"] or not selected["year"]:
        flash("Select an antigen and year before downloading.", "warning")
        return redirect(url_for("vax_rates.vaccination_rates"))

    if request.args.get("download") == "regions":
        rows = get_regions_summary(**selected, sort_col="countries_met", order="desc")
        return _csv_response(rows, ["antigen", "year", "region", "countries_met"], "regions-meeting-target.csv")

    rows = get_countries_meeting_target(**selected, sort_col=sort, order=order)
    return _csv_response(rows, ["antigen", "year", "country", "region", "pct_of_target"], "countries-meeting-target.csv")


def _csv_response(rows, columns, filename):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(column, "") for column in columns])
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
