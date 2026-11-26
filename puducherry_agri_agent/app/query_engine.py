"""Answer plain-English questions from the SQLite knowledge base (the KB 'ASK' step).
Keyword rules pick the intent, location_aliases resolves place names, and a parameterised
SQL query fetches the answer together with its provenance (source, file, page/table).

Intents:  value | compare (spatial) | trend (temporal) | provenance | coop | lgd
Optional: if no rule matches and ANTHROPIC_API_KEY is set, an LLM maps the question to the
same parameters (it never writes SQL and never invents numbers). Offline, this is skipped.
"""
import json
import os
import re
import sqlite3
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT / "db" / "puducherry_agri.db"
REGIONS = ["Puducherry", "Karaikal", "Mahe", "Yanam"]
YEAR_RX = re.compile(r"20\d\d-\d\d")
LLM_MODEL = "claude-opus-5-5"

METRIC_WORDS = [("yield", "yield_value"), ("production", "production_value"),
                ("produced", "production_value"), ("out-turn", "production_value"),
                ("outturn", "production_value"), ("tonnes", "production_value"),
                ("area", "area_ha"), ("hectare", "area_ha")]
METRIC_LABEL = {"area_ha": "area", "yield_value": "yield", "production_value": "production"}
CROP_WORDS = {"paddy": "Paddy", "rice": "Paddy", "sugarcane": "Sugarcane", "banana": "Banana/Plantain",
              "plantain": "Banana/Plantain", "coconut": "Coconut", "groundnut": "Groundnut",
              "cotton": "Cotton", "mango": "Mango", "tapioca": "Tapioca", "brinjal": "Brinjal",
              "black gram": "Black gram", "blackgram": "Black gram", "green gram": "Green gram",
              "ragi": "Ragi", "cashew": "Cashewnut", "sesamum": "Sesamum (gingelly)",
              "gingelly": "Sesamum (gingelly)", "guava": "Guava", "onion": "Onion",
              "net area sown": "Net area sown"}


def connect(path=DB_PATH):
    """Open the knowledge base read-only-style (rows behave like dicts)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ----------------------------------------------------------------------------- understanding
def find_regions(conn, question):
    """Return the canonical regions named in the question, looked up in location_aliases.
    Words and word pairs are tried, so 'Pondicherry', 'KKL' or 'Yanaon' all work."""
    words = re.findall(r"[A-Za-zé]+", question)
    phrases = words + [a + " " + b for a, b in zip(words, words[1:])]
    found = []
    for phrase in phrases:
        key = re.sub(r"[^a-z]", "", phrase.lower().replace("é", "e"))
        row = conn.execute("SELECT canonical_name FROM location_aliases WHERE alias_key = ? "
                           "AND entity_type = 'region'", (key,)).fetchone()
        if row and row[0] not in found:
            found.append(row[0])
    if re.search(r"\b(UT|union territory|whole territory|state total)\b", question, re.I):
        found.append("UT")
    return found


def parse_question(conn, question):
    """Turn a question into parameters: intent, crop, metric, regions and years.
    Pure keyword rules, so the same question always gives the same parameters."""
    q = question.lower()
    params = {"crop": next((c for w, c in CROP_WORDS.items() if w in q), None),
              "metric": next((m for w, m in METRIC_WORDS if w in q), "production_value"),
              "regions": find_regions(conn, question), "years": YEAR_RX.findall(question)}
    if re.search(r"source|which page|which table|come from|provenance|where does", q):
        params["intent"] = "provenance"
    elif re.search(r"co-?op|societ", q):
        params["intent"] = "coop"
    elif re.search(r"\blgd\b|district|sub-district|village", q):
        params["intent"] = "lgd"
    elif params["crop"] and (re.search(r"trend|change|over the years|from 20", q) or len(params["years"]) > 1):
        params["intent"] = "trend"
    elif params["crop"] and re.search(r"compare|which region|highest|lowest|largest|smallest|rank", q):
        params["intent"] = "compare"
    elif params["crop"]:
        params["intent"] = "value"
    else:
        params["intent"] = None
    return params


def llm_parse(question):
    """Optional fallback: ask Claude to fill the same parameter dict as JSON.
    Returns None when no API key / SDK is available or the answer is not usable."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=LLM_MODEL, max_tokens=1024, output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=[{"role": "user", "content": (
                "Map this question about Puducherry crop statistics to JSON with keys intent "
                "(value|compare|trend|provenance|coop|lgd), crop, metric "
                "(area_ha|yield_value|production_value), regions (list of Puducherry, Karaikal, "
                "Mahe, Yanam, UT), years (list like 2021-22). Reply with JSON only.\n\n" + question)}])
        if response.stop_reason == "refusal":
            return None
        text = next((b.text for b in response.content if b.type == "text"), "")
        return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except Exception:  # noqa: BLE001 - the fallback is optional and must never crash the CLI
        return None


# ----------------------------------------------------------------------------- answering
def result(question, params, answer, sql, sql_params, rows):
    """Package one answer: text, the SQL that ran, its rows and their provenance."""
    provenance = []
    for r in rows:
        item = {"source_id": r["source_id"], "source_file_or_url": r["source_file_or_url"],
                "page_or_table": r["page_or_table"]}
        if item not in provenance:
            provenance.append(item)
    return {"question": question, "intent": params["intent"], "params": params, "answer": answer,
            "sql": " ".join(sql.split()), "sql_params": list(sql_params),
            "rows": [dict(r) for r in rows], "provenance": provenance}


def crop_rows(conn, crop, metric, regions, years):
    """Run the one crop_statistics query every crop intent uses; returns (sql, params, rows)."""
    sql = (f"SELECT crop_year, region, crop, {metric} AS value, extraction_method, source_id, "
           f"source_file_or_url, page_or_table FROM crop_statistics WHERE crop = ? AND season = 'All' "
           f"AND region IN ({','.join('?' * len(regions))}) AND crop_year IN ({','.join('?' * len(years))}) "
           f"ORDER BY crop_year, region")
    args = [crop, *regions, *years]
    return sql, args, conn.execute(sql, args).fetchall()


def all_years(conn):
    """Return every crop year in the KB, oldest first."""
    return [r[0] for r in conn.execute("SELECT DISTINCT crop_year FROM crop_statistics ORDER BY 1")]


def unit_of(crop, metric):
    """Return the printed unit for a crop metric (coconut is counted in nuts)."""
    if metric == "area_ha":
        return "ha"
    if metric == "yield_value":
        return "nuts/ha" if crop == "Coconut" else "kg/ha"
    return "thousand nuts" if crop == "Coconut" else "tonnes"


def answer_value(conn, question, p):
    """One crop number per region and year (defaults: UT, latest year)."""
    regions = p["regions"] or ["UT"]
    years = p["years"] or all_years(conn)[-1:]
    sql, args, rows = crop_rows(conn, p["crop"], p["metric"], regions, years)
    unit = unit_of(p["crop"], p["metric"])
    parts = [f"{r['region']} {r['crop_year']}: {r['value']:,.0f} {unit}" for r in rows]
    text = f"{p['crop']} {METRIC_LABEL[p['metric']]} - " + "; ".join(parts) if parts else "No matching rows."
    return result(question, p, text, sql, args, rows)


def answer_compare(conn, question, p):
    """Spatial question: the 4 regions side by side for one year, ranked high to low."""
    year = (p["years"] or all_years(conn)[-1:])[0]
    regions = [r for r in p["regions"] if r != "UT"] or REGIONS
    sql, args, rows = crop_rows(conn, p["crop"], p["metric"], regions, [year])
    ranked = sorted(rows, key=lambda r: r["value"] or 0, reverse=True)
    unit = unit_of(p["crop"], p["metric"])
    if not ranked:
        return result(question, p, "No matching rows.", sql, args, rows)
    listing = ", ".join(f"{r['region']} {r['value']:,.0f}" for r in ranked)
    text = (f"{year} {p['crop']} {METRIC_LABEL[p['metric']]} ({unit}): {listing}. "
            f"Highest: {ranked[0]['region']}; lowest: {ranked[-1]['region']}.")
    return result(question, p, text, sql, args, rows)


def answer_trend(conn, question, p):
    """Temporal question: one region's series over the years, with the overall change."""
    region = (p["regions"] or ["UT"])[0]
    years = all_years(conn)
    if len(p["years"]) >= 2:
        years = [y for y in years if min(p["years"]) <= y <= max(p["years"])]
    sql, args, rows = crop_rows(conn, p["crop"], p["metric"], [region], years)
    unit = unit_of(p["crop"], p["metric"])
    if len(rows) < 2:
        return result(question, p, "Not enough years in the KB for a trend.", sql, args, rows)
    first, last = rows[0]["value"], rows[-1]["value"]
    change = f"{(last - first) / first:+.1%}" if first else "n/a"
    series = ", ".join(f"{r['crop_year']} {r['value']:,.0f}" for r in rows)
    text = (f"{region} {p['crop']} {METRIC_LABEL[p['metric']]} ({unit}): {series}. "
            f"Change {rows[0]['crop_year']} -> {rows[-1]['crop_year']}: {change}.")
    return result(question, p, text, sql, args, rows)


def answer_provenance(conn, question, p):
    """Say exactly which file, page, table and column a number came from, and how it was read."""
    region = (p["regions"] or ["UT"])[0]
    year = (p["years"] or all_years(conn)[-1:])[0]
    sql, args, rows = crop_rows(conn, p["crop"], p["metric"], [region], [year])
    if not rows:
        return result(question, p, "No matching row.", sql, args, rows)
    r = rows[0]
    table = {"area_ha": "IV-A", "yield_value": "V-A", "production_value": "V-B"}[p["metric"]]
    page = next((part for part in r["page_or_table"].split("; ") if f"Table {table} " in part),
                r["page_or_table"])
    text = (f"{year} {region} {p['crop']} {METRIC_LABEL[p['metric']]} = {r['value']:,.0f} "
            f"{unit_of(p['crop'], p['metric'])}. Source {r['source_id']}: {r['source_file_or_url']}, "
            f"{page} (read with {r['extraction_method']}).")
    return result(question, p, text, sql, args, rows)


def answer_coop(conn, question, p):
    """Count working and dormant credit co-operative societies per region (S6)."""
    sql = ("SELECT region, status, COUNT(*) AS n, MIN(source_id) AS source_id, "
           "MIN(source_file_or_url) AS source_file_or_url, "
           "'table 1 (working) + table 2 (dormant)' AS page_or_table "
           "FROM coop_societies GROUP BY region, status ORDER BY region, status")
    rows = conn.execute(sql).fetchall()
    counts = {region: {"working": 0, "dormant": 0} for region in REGIONS}
    for r in rows:
        counts[r["region"]][r["status"]] = r["n"]
    parts = [f"{reg} {c['working']} working + {c['dormant']} dormant" for reg, c in counts.items()]
    total = sum(r["n"] for r in rows)
    text = f"{total} credit co-operative societies: " + "; ".join(parts) + "."
    return result(question, p, text, sql, [], rows)


def answer_lgd(conn, question, p):
    """Explain the LGD hierarchy: 2 LGD districts versus the 4 reporting regions (S7)."""
    sql = ("SELECT entity_type, name, lgd_code, lgd_district_code, region, source_id, "
           "source_file_or_url, page_or_table FROM lgd_locations "
           "WHERE entity_type IN ('district', 'region') OR (entity_type = 'subdistrict' "
           "AND name IN ('Mahe', 'Yanam')) ORDER BY entity_type, name")
    rows = conn.execute(sql).fetchall()
    districts = [f"{r['name']} ({r['lgd_code']})" for r in rows if r["entity_type"] == "district"]
    regions = [r["name"] for r in rows if r["entity_type"] == "region"]
    subs = [f"{r['name']} ({r['lgd_code']})" for r in rows if r["entity_type"] == "subdistrict"]
    text = (f"LGD lists {len(districts)} districts: {', '.join(districts)}. The reports use "
            f"{len(regions)} regions: {', '.join(regions)}. {' and '.join(subs)} are LGD "
            f"sub-districts of district 600, so they are stored with district 600 + their "
            f"sub-district code.")
    return result(question, p, text, sql, [], rows)


HANDLERS = {"value": answer_value, "compare": answer_compare, "trend": answer_trend,
            "provenance": answer_provenance, "coop": answer_coop, "lgd": answer_lgd}


def ask(question, conn=None):
    """Main entry point: question in, answer dict out (answer, sql, rows, provenance).
    Uses the keyword rules first and the optional LLM parser only if they find nothing."""
    own = conn is None
    conn = conn or connect()
    params = parse_question(conn, question)
    if params["intent"] is None:
        params = llm_parse(question) or params
    handler = HANDLERS.get(params.get("intent"))
    if handler is None:
        out = result(question, {"intent": None}, "Sorry, I could not understand the question. Try "
                     "naming a crop (paddy, sugarcane ...), a region and a year such as 2023-24.",
                     "", [], [])
    else:
        out = handler(conn, question, params)
    if own:
        conn.close()
    return out


def format_answer(out):
    """Turn an answer dict into the text block printed by run.py."""
    lines = [f"Q: {out['question']}", f"A: {out['answer']}", f"   intent: {out['intent']}",
             f"   SQL: {out['sql']}", f"   params: {out['sql_params']}"]
    for item in out["provenance"][:6]:
        lines.append(f"   provenance: {item['source_id']} | {item['source_file_or_url']} | "
                     f"{item['page_or_table']}")
    if len(out["provenance"]) > 6:
        lines.append(f"   ... {len(out['provenance']) - 6} more provenance rows")
    return "\n".join(lines)
