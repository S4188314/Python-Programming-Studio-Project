# db_queries.py
# Purpose: every SQL query in the project lives here as a named function.

from db_connection import get_connection


# -----------------------------------------------------------------------
# FORMATTERS AND SHARED HELPERS
# -----------------------------------------------------------------------

def _fetch_all(sql, params=None):
    with get_connection() as conn:
        rows = conn.execute(sql, params or {}).fetchall()
    return [dict(row) for row in rows]


def _fetch_one(sql, params=None):
    with get_connection() as conn:
        row = conn.execute(sql, params or {}).fetchone()
    return dict(row) if row else {}


def _format_int(value):
    return f"{round(float(value or 0)):,.0f}"


def _format_decimal(value, digits=1):
    return f"{float(value or 0):,.{digits}f}"


def _compact_number(value):
    value = float(value or 0)
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    return _format_int(value)


def _clean_order(order):
    return order if order in {"asc", "desc"} else "desc"


def _sort_sql(sort_col, allowed_sorts, default_sort):
    return allowed_sorts.get(sort_col, allowed_sorts[default_sort])


def _rate_band(value):
    if value >= 10:
        return "risk-high", "High"
    if value >= 1:
        return "risk-mid", "Moderate"
    return "risk-low", "Low"


def _target_band(value):
    if value >= 100:
        return "target-strong", "At or above 100%"
    return "target-met", "Met 90% threshold"


def _increase_band(value):
    if value > 5:
        return "increase-strong", "Strong gain"
    if value >= 2:
        return "increase-medium", "Moderate gain"
    return "increase-soft", "Small gain"


def _bar_level(ratio):
    if ratio >= 10:
        return "bar-level-5"
    if ratio >= 5:
        return "bar-level-4"
    if ratio >= 2:
        return "bar-level-3"
    if ratio >= 1.2:
        return "bar-level-2"
    return "bar-level-1"


def _format_antigen_rows(rows):
    return [{"code": row["code"], "name": row["name"]} for row in rows]


# -----------------------------------------------------------------------
# SHARED / UTILITY QUERIES
# -----------------------------------------------------------------------

def get_all_antigens():
    sql = "SELECT AntigenID AS code, name FROM Antigen ORDER BY AntigenID"
    return _format_antigen_rows(_fetch_all(sql))


def get_all_years():
    sql = "SELECT YearID AS year FROM YearDate ORDER BY YearID DESC"
    return [row["year"] for row in _fetch_all(sql)]


def get_year_range():
    sql = "SELECT MIN(YearID) AS min_year, MAX(YearID) AS max_year FROM YearDate"
    row = _fetch_one(sql)
    return row["min_year"], row["max_year"]


def get_all_regions():
    sql = "SELECT region AS name FROM Region ORDER BY region"
    return [row["name"] for row in _fetch_all(sql)]


def get_all_countries():
    sql = "SELECT CountryID AS code, name FROM Country ORDER BY name"
    return _fetch_all(sql)


def get_all_economies():
    sql = "SELECT phase FROM Economy ORDER BY economyID"
    return [row["phase"] for row in _fetch_all(sql)]


def get_all_diseases():
    sql = "SELECT id AS code, description AS name FROM Infection_Type ORDER BY description"
    return _fetch_all(sql)


def get_vaccination_anomaly_count():
    sql = """
        SELECT COUNT(*) AS issues
        FROM Vaccination
        WHERE target_num = '' OR doses = '' OR coverage = ''
    """
    return _fetch_one(sql)["issues"]


def get_infection_anomaly_count():
    sql = """
        SELECT COUNT(*) AS issues
        FROM InfectionData i
        LEFT JOIN CountryPopulation p
          ON i.country = p.country AND i.year = p.year
        WHERE i.cases IS NULL
           OR p.population IS NULL
           OR p.population = ''
           OR CAST(p.population AS REAL) <= 0
    """
    return _fetch_one(sql)["issues"]


# -----------------------------------------------------------------------
# PAGE 1 - LANDING
# -----------------------------------------------------------------------

def get_landing_stats():
    vax_sql = """
        SELECT MIN(year) AS min_year,
               MAX(year) AS max_year,
               SUM(CASE WHEN doses != '' THEN CAST(doses AS REAL) ELSE 0 END) AS total_doses
        FROM Vaccination
    """
    infection_sql = "SELECT SUM(cases) AS total_cases FROM InfectionData"
    disease_sql = "SELECT COUNT(*) AS disease_count FROM Infection_Type"
    country_sql = "SELECT COUNT(*) AS country_count FROM Country"

    vax = _fetch_one(vax_sql)
    infections = _fetch_one(infection_sql)
    diseases = _fetch_one(disease_sql)
    countries = _fetch_one(country_sql)

    return {
        "timeframe": f"{vax['min_year']}-{vax['max_year']}",
        "total_doses": _compact_number(vax["total_doses"]),
        "total_cases": _compact_number(infections["total_cases"]),
        "disease_count": _format_int(diseases["disease_count"]),
        "country_count": _format_int(countries["country_count"]),
    }


def get_disease_list():
    sql = """
        SELECT it.id AS code,
               it.description AS name,
               SUM(i.cases) AS total_cases
        FROM Infection_Type it
        LEFT JOIN InfectionData i ON it.id = i.inf_type
        GROUP BY it.id, it.description
        ORDER BY it.description
    """
    rows = _fetch_all(sql)
    for row in rows:
        row["total_cases_display"] = _compact_number(row["total_cases"])
    return rows


# -----------------------------------------------------------------------
# PAGE 2 - MISSION
# -----------------------------------------------------------------------

def get_personas():
    sql = """
        SELECT name,
               role,
               age,
               tech_proficiency,
               goals,
               pain_points,
               explanation
        FROM personas
        ORDER BY id
    """
    return _fetch_all(sql)


def get_team_members():
    sql = "SELECT name, student_id FROM team_members ORDER BY id"
    return _fetch_all(sql)


# -----------------------------------------------------------------------
# PAGE 3 - VACCINATION RATES
# -----------------------------------------------------------------------

def get_countries_meeting_target(antigen, year, region, country, sort_col, order):
    allowed_sorts = {
        "antigen": "v.antigen",
        "year": "v.year",
        "country": "c.name",
        "region": "r.region",
        "pct_of_target": "pct_of_target",
    }
    sort_sql = _sort_sql(sort_col, allowed_sorts, "pct_of_target")
    order = _clean_order(order)
    region_filter = "AND r.region = :region" if region else ""
    country_filter = "AND c.CountryID = :country" if country else ""

    sql = f"""
        SELECT v.antigen,
               a.name AS antigen_name,
               v.year,
               c.name AS country,
               c.CountryID AS country_code,
               r.region,
               ROUND(AVG(CAST(v.coverage AS REAL)), 1) AS pct_of_target
        FROM Vaccination v
        JOIN Antigen a ON v.antigen = a.AntigenID
        JOIN Country c ON v.country = c.CountryID
        JOIN Region r ON c.region = r.RegionID
        WHERE v.antigen = :antigen
          AND v.year = :year
          AND v.coverage != ''
          {region_filter}
          {country_filter}
        GROUP BY v.antigen, a.name, v.year, c.name, c.CountryID, r.region
        HAVING pct_of_target >= 90
        ORDER BY {sort_sql} {order}
    """
    rows = _fetch_all(sql, {"antigen": antigen, "year": year, "region": region, "country": country})
    for row in rows:
        row["pct_display"] = _format_decimal(row["pct_of_target"])
        row["target_class"], row["target_status"] = _target_band(row["pct_of_target"])
    return rows


def get_regions_summary(antigen, year, region, country, sort_col, order):
    allowed_sorts = {
        "region": "region",
        "countries_met": "countries_met",
        "avg_coverage": "avg_coverage",
    }
    sort_sql = _sort_sql(sort_col, allowed_sorts, "countries_met")
    order = _clean_order(order)
    region_filter = "AND r.region = :region" if region else ""
    country_filter = "AND c.CountryID = :country" if country else ""

    sql = f"""
        WITH country_rates AS (
            SELECT v.antigen,
                   a.name AS antigen_name,
                   v.year,
                   c.CountryID,
                   r.region,
                   AVG(CAST(v.coverage AS REAL)) AS coverage_pct
            FROM Vaccination v
            JOIN Antigen a ON v.antigen = a.AntigenID
            JOIN Country c ON v.country = c.CountryID
            JOIN Region r ON c.region = r.RegionID
            WHERE v.antigen = :antigen
              AND v.year = :year
              AND v.coverage != ''
              {region_filter}
              {country_filter}
            GROUP BY v.antigen, a.name, v.year, c.CountryID, r.region
        )
        SELECT antigen,
               antigen_name,
               year,
               region,
               COUNT(*) AS countries_met,
               ROUND(AVG(coverage_pct), 1) AS avg_coverage
        FROM country_rates
        WHERE coverage_pct >= 90
        GROUP BY antigen, antigen_name, year, region
        ORDER BY {sort_sql} {order}
    """
    rows = _fetch_all(sql, {"antigen": antigen, "year": year, "region": region, "country": country})
    for row in rows:
        row["countries_met_display"] = _format_int(row["countries_met"])
        row["avg_coverage_display"] = _format_decimal(row["avg_coverage"])
    return rows


# -----------------------------------------------------------------------
# PAGE 4 - INFECTION BY ECONOMY
# -----------------------------------------------------------------------

def get_infection_by_country(status, disease, year, sort_col, order):
    allowed_sorts = {
        "disease": "it.description",
        "country": "c.name",
        "economic_phase": "e.phase",
        "year": "i.year",
        "cases_per_100k": "cases_per_100k",
    }
    sort_sql = _sort_sql(sort_col, allowed_sorts, "cases_per_100k")
    order = _clean_order(order)

    sql = f"""
        SELECT it.description AS disease,
               c.name AS country,
               e.phase AS economic_phase,
               i.year,
               ROUND(i.cases * 100000.0 / CAST(p.population AS REAL), 2) AS cases_per_100k
        FROM InfectionData i
        JOIN Infection_Type it ON i.inf_type = it.id
        JOIN Country c ON i.country = c.CountryID
        JOIN Economy e ON c.economy = e.economyID
        JOIN CountryPopulation p ON i.country = p.country AND i.year = p.year
        WHERE e.phase = :status
          AND i.inf_type = :disease
          AND i.year = :year
          AND p.population != ''
        ORDER BY {sort_sql} {order}
    """
    rows = _fetch_all(sql, {"status": status, "disease": disease, "year": year})
    for row in rows:
        row["rate_display"] = _format_decimal(row["cases_per_100k"], 2)
        row["risk_class"], row["risk_label"] = _rate_band(row["cases_per_100k"])
    return rows


def get_infection_summary_by_economy(status, disease, year, sort_col, order):
    allowed_sorts = {
        "disease": "it.description",
        "economic_phase": "e.phase",
        "year": "i.year",
        "total_cases": "total_cases",
    }
    sort_sql = _sort_sql(sort_col, allowed_sorts, "total_cases")
    order = _clean_order(order)

    sql = f"""
        SELECT it.description AS disease,
               e.phase AS economic_phase,
               i.year,
               SUM(i.cases) AS total_cases,
               COUNT(DISTINCT c.CountryID) AS countries
        FROM InfectionData i
        JOIN Infection_Type it ON i.inf_type = it.id
        JOIN Country c ON i.country = c.CountryID
        JOIN Economy e ON c.economy = e.economyID
        WHERE e.phase = :status
          AND i.inf_type = :disease
          AND i.year = :year
        GROUP BY it.description, e.phase, i.year
        ORDER BY {sort_sql} {order}
    """
    rows = _fetch_all(sql, {"status": status, "disease": disease, "year": year})
    for row in rows:
        row["total_cases_display"] = _format_int(row["total_cases"])
        row["countries_display"] = _format_int(row["countries"])
    return rows


def get_infection_summary_cards(status, disease, year):
    sql = """
        WITH scoped AS (
            SELECT i.cases,
                   i.cases * 100000.0 / CAST(p.population AS REAL) AS rate,
                   c.CountryID
            FROM InfectionData i
            JOIN Country c ON i.country = c.CountryID
            JOIN Economy e ON c.economy = e.economyID
            JOIN CountryPopulation p ON i.country = p.country AND i.year = p.year
            WHERE e.phase = :status
              AND i.inf_type = :disease
              AND i.year = :year
              AND p.population != ''
        )
        SELECT SUM(cases) AS total_cases,
               AVG(rate) AS avg_rate,
               COUNT(DISTINCT CountryID) AS countries
        FROM scoped
    """
    row = _fetch_one(sql, {"status": status, "disease": disease, "year": year})
    return [
        {"label": "Total Cases", "value": _format_int(row["total_cases"]), "note": "within selected economy"},
        {"label": "Average per 100,000", "value": _format_decimal(row["avg_rate"], 2), "note": "country-level average"},
        {"label": "Countries Shown", "value": _format_int(row["countries"]), "note": "matching all filters"},
    ]


# -----------------------------------------------------------------------
# PAGE 5 - VACCINATION IMPROVEMENT
# -----------------------------------------------------------------------

def get_top_improving_countries(antigen, start_year, end_year, top_n):
    top_n = int(top_n)
    sql = """
        WITH rates AS (
            SELECT c.name AS country,
                   v.year,
                   AVG(CAST(v.doses AS REAL) * 100.0 / CAST(p.population AS REAL)) AS vax_rate
            FROM Vaccination v
            JOIN Country c ON v.country = c.CountryID
            JOIN CountryPopulation p ON v.country = p.country AND v.year = p.year
            WHERE v.antigen = :antigen
              AND v.year IN (:start_year, :end_year)
              AND v.doses != ''
              AND p.population != ''
            GROUP BY c.CountryID, c.name, v.year
        )
        SELECT r_start.country,
               ROUND(r_start.vax_rate, 2) AS start_rate,
               ROUND(r_end.vax_rate, 2) AS end_rate,
               ROUND(r_end.vax_rate - r_start.vax_rate, 2) AS rate_increase,
               :start_year AS start_year,
               :end_year AS end_year
        FROM rates r_start
        JOIN rates r_end ON r_start.country = r_end.country
        WHERE r_start.year = :start_year
          AND r_end.year = :end_year
          AND rate_increase > 0
        ORDER BY rate_increase DESC
        LIMIT :top_n
    """
    rows = _fetch_all(sql, {
        "antigen": antigen,
        "start_year": start_year,
        "end_year": end_year,
        "top_n": top_n,
    })
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        row["rank_label"] = str(index)
        row["start_rate_display"] = _format_decimal(row["start_rate"], 2)
        row["end_rate_display"] = _format_decimal(row["end_rate"], 2)
        row["increase_display"] = _format_decimal(row["rate_increase"], 2)
        row["increase_class"], row["increase_label"] = _increase_band(row["rate_increase"])
        row["bar_class"] = _bar_level(max(row["rate_increase"], 1))
        row["medal_class"] = "medal-top" if index <= 3 else "medal-standard"
    return rows


# -----------------------------------------------------------------------
# PAGE 6 - ABOVE AVERAGE INFECTION
# -----------------------------------------------------------------------

def get_countries_above_global_average(disease, year):
    sql = """
        WITH rates AS (
            SELECT c.name AS country,
                   it.description AS infection_type,
                   i.year,
                   i.cases * 100000.0 / CAST(p.population AS REAL) AS per_100k
            FROM InfectionData i
            JOIN Infection_Type it ON i.inf_type = it.id
            JOIN Country c ON i.country = c.CountryID
            JOIN CountryPopulation p ON i.country = p.country AND i.year = p.year
            WHERE i.inf_type = :disease
              AND i.year = :year
              AND p.population != ''
        ),
        global_rate AS (
            SELECT AVG(per_100k) AS global_avg FROM rates
        )
        SELECT country,
               infection_type,
               year,
               ROUND(per_100k, 2) AS per_100k,
               ROUND((SELECT global_avg FROM global_rate), 2) AS global_avg,
               per_100k / NULLIF((SELECT global_avg FROM global_rate), 0) AS ratio
        FROM rates
        WHERE per_100k > (SELECT global_avg FROM global_rate)
        ORDER BY per_100k DESC
    """
    rows = _fetch_all(sql, {"disease": disease, "year": year})
    global_rate = rows[0]["global_avg"] if rows else _get_global_rate(disease, year)
    disease_name = _get_disease_name(disease)
    table_rows = [_global_average_row(disease_name, year, global_rate)]

    for row in rows:
        row["per_100k_display"] = _format_decimal(row["per_100k"], 2)
        row["bar_class"] = _bar_level(row["ratio"])
        row["row_class"] = ""
        table_rows.append(row)
    return table_rows, global_rate


def _get_global_rate(disease, year):
    sql = """
        SELECT ROUND(AVG(i.cases * 100000.0 / CAST(p.population AS REAL)), 2) AS global_avg
        FROM InfectionData i
        JOIN CountryPopulation p ON i.country = p.country AND i.year = p.year
        WHERE i.inf_type = :disease
          AND i.year = :year
          AND p.population != ''
    """
    return _fetch_one(sql, {"disease": disease, "year": year})["global_avg"]


def _get_disease_name(disease):
    sql = "SELECT description AS name FROM Infection_Type WHERE id = :disease"
    return _fetch_one(sql, {"disease": disease}).get("name", disease)


def _global_average_row(disease_name, year, global_rate):
    return {
        "country": "Global",
        "infection_type": disease_name,
        "year": year,
        "per_100k": global_rate,
        "per_100k_display": _format_decimal(global_rate, 2),
        "bar_class": "bar-level-1",
        "row_class": "global-row",
    }
