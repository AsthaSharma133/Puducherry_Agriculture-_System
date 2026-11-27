"""Draw the 5 report/poster figures (300 dpi PNG) into docs/figures/ with plain matplotlib.
Every number comes from eval/results_by_agent*.csv, db/puducherry_agri.db or db/schema.sql.

  fig_extraction_f1.png             per-agent precision / recall / F1 with n annotated
  fig_spatiotemporal_crop_trends.png paddy & sugarcane area, production, yield by region 2020-21..2024-25
  fig_architecture.png              Sources -> Supervisor -> A1/A2/A3 -> Normalizer -> SQLite KB -> Query engine
  fig_er_diagram.png                tables, keys and logical links of db/schema.sql
  fig_qlora_base_vs_adapter.png     base Qwen2.5-1.5B vs QLoRA adapter F1 (eval/adapter_comparison.csv)

Run (from puducherry_agri_agent/):  python scripts/generate_figures.py
"""
import csv
import json
import re
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                       # draw to files, no window needed
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
from matplotlib.patches import FancyBboxPatch  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "docs" / "figures"
DPI = 300
# Validated categorical slots (blue, orange, aqua) + text inks; checked with the dataviz validator
BLUE, ORANGE, AQUA = "#257de0", "#f47230", "#00b894"
INK, INK_2, GRID = "#191919", "#666666", "#e5e5e5"
plt.rcParams.update({"font.size": 14, "axes.titlesize": 16, "axes.labelsize": 14,
                     "axes.edgecolor": INK_2, "axes.labelcolor": INK, "xtick.color": INK_2,
                     "ytick.color": INK_2, "axes.spines.top": False, "axes.spines.right": False})


def read_csv(path):
    """Return the rows of a CSV file as a list of dicts."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ----------------------------------------------------------------------------- figure 1
def fig_extraction_f1():
    """Grouped bars of precision, recall and F1 per agent, with n cases / n fields under each group.
    Adds A3 before the reg_no fix so the effect of the bug found by the evaluation is visible."""
    rows = [r for r in read_csv(PROJECT / "eval" / "results_by_agent.csv") if r["agent"] != "MACRO"]
    before = {r["agent"]: r for r in read_csv(PROJECT / "eval" / "results_by_agent_before_s6_fix.csv")}
    groups = [(r["agent"], r) for r in rows] + [("A3\nbefore fix", before["A3"])]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    width = 0.26
    for i, (metric, color) in enumerate([("precision", BLUE), ("recall", ORANGE), ("f1", AQUA)]):
        xs = [g + (i - 1) * (width + 0.02) for g in range(len(groups))]
        vals = [float(r[metric]) for _, r in groups]
        ax.bar(xs, vals, width, color=color, label=metric.capitalize() if metric != "f1" else "F1")
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.012, f"{v:.3f}", ha="center", va="bottom", fontsize=11, color=INK)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([f"{name}\nn={r['n_cases']} cases, {r['n_fields']} fields" for name, r in groups])
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Field-level score")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    n_cases = sum(int(r["n_cases"]) for r in rows)
    n_fields = sum(int(r["n_fields"]) for r in rows)
    ax.set_title(f"Extraction accuracy on eval/eval_set.json ({n_cases} cases, {n_fields} fields)", loc="left")
    ax.legend(loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.text(0.01, -0.04, "All cases real: A1 = S2 prices (live page), A2 = S3 PDF tables (12 OCR + 4 "
             "text-layer columns), A3 = S6 co-ops + S5 schemes (live pages)", fontsize=10, color=INK_2)
    save(fig, "fig_extraction_f1.png")


# ----------------------------------------------------------------------------- figure 2
def crop_series(conn, crop, metric, region):
    """Return (years, values) of one crop metric for one region from crop_statistics."""
    rows = conn.execute(f"SELECT crop_year, {metric} FROM crop_statistics WHERE crop = ? AND "
                        f"region = ? AND season = 'All' ORDER BY crop_year", (crop, region)).fetchall()
    return [r[0] for r in rows], [r[1] for r in rows]


def label_offset(value, others, top):
    """Place a value label by rank among the regions in the same year so labels never collide:
    highest above the point, lowest below it (above if near zero), a middle value to the right."""
    if all(value >= o for o in others) or value < 0.1 * top:
        return (0, 9), "center", "bottom"
    if all(value <= o for o in others):
        return (0, -10), "center", "top"
    return (10, 0), "left", "center"


def draw_panel(ax, conn, crop, metric, regions, title, unit):
    """Draw one small-multiple panel: one line per region with every value labelled."""
    series = {region: crop_series(conn, crop, metric, region) for region, _c, _m in regions}
    top = max(v for _years, vals in series.values() for v in vals)
    for region, color, marker in regions:
        years, vals = series[region]
        ax.plot(years, vals, color=color, linewidth=2, marker=marker, markersize=8, label=region)
        for i, (x, v) in enumerate(zip(years, vals)):
            others = [series[r][1][i] for r in series if r != region]
            offset, ha, va = label_offset(v, others, top)
            ax.annotate(f"{v:,.0f}", (x, v), textcoords="offset points", xytext=offset,
                        ha=ha, va=va, fontsize=9, color=INK)
    ax.set_title(f"{title} ({unit})", loc="left", fontsize=14)
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=10)
    ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    ax.margins(x=0.08, y=0.2)
    if metric != "yield_value":
        ax.set_ylim(bottom=0)


def fig_crop_trends():
    """Small multiples: rows = Paddy, Sugarcane; columns = area, production, yield.
    Paddy shows the 3 regions that grow it; sugarcane is grown only in Puducherry region."""
    conn = sqlite3.connect(PROJECT / "db" / "puducherry_agri.db")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10.5))
    paddy = [("Puducherry", BLUE, "o"), ("Karaikal", ORANGE, "s"), ("Yanam", AQUA, "^")]
    cane = [("Puducherry", BLUE, "o")]
    metrics = [("area_ha", "Area", "ha"), ("production_value", "Production", "tonnes"),
               ("yield_value", "Yield", "kg/ha")]
    for col, (metric, label, unit) in enumerate(metrics):
        draw_panel(axes[0][col], conn, "Paddy", metric, paddy, f"Paddy {label.lower()}", unit)
        draw_panel(axes[1][col], conn, "Sugarcane", metric, cane, f"Sugarcane {label.lower()}", unit)
    conn.close()
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, frameon=False, fontsize=13,
               bbox_to_anchor=(0.99, 0.985))
    fig.suptitle("Region-wise crop trends, Puducherry UT, 2020-21 to 2024-25 (S3 Season & Crop Reports)",
                 x=0.01, ha="left", fontsize=18)
    fig.text(0.01, 0.005, "Mahe grows neither crop (all values 0); Karaikal, Mahe and Yanam grow no "
             "sugarcane. 2021-22 values were read by OCR from vector-outline pages. Source: "
             "db/puducherry_agri.db crop_statistics (provenance per row).", fontsize=11, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    save(fig, "fig_spatiotemporal_crop_trends.png")


# ----------------------------------------------------------------------------- figure 3
def box(ax, x, y, w, h, title, body="", color=BLUE):
    """Draw a rounded block with a bold title and optional smaller body text."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                facecolor="white", edgecolor=color, linewidth=2.5))
    ax.text(x + w / 2, y + h - 0.22, title, ha="center", va="top", fontsize=14, weight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h - 0.62, body, ha="center", va="top", fontsize=10.5, color=INK_2,
                linespacing=1.35)


def arrow(ax, start, end, label=""):
    """Draw an arrow between two points with an optional label at its middle."""
    ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-|>", color=INK_2, lw=2))
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.12, label, ha="center",
                fontsize=10, color=INK_2)


def fig_architecture():
    """Block diagram of the pipeline from sources to the query engine."""
    fig, ax = plt.subplots(figsize=(18, 9))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 9)
    ax.axis("off")
    box(ax, 0.3, 2.2, 3.2, 5.0, "Sources", "S2 prices (HTML)\nS3 Season & Crop\nReports (PDF)\n"
        "S5 schemes (HTML)\nS6 co-op societies\n(HTML)\nS7 LGD codes\nS8 Agromet bulletins\n(PDF)", ORANGE)
    box(ax, 4.4, 3.7, 3.0, 2.0, "Supervisor", "orchestrator: routes by\nmanifest, retries,\nlogs pipeline_runs")
    box(ax, 8.3, 6.2, 3.0, 1.9, "Agent A1", "prices\nBeautifulSoup")
    box(ax, 8.3, 3.7, 3.0, 2.0, "Agent A2", "PDF tables: PyMuPDF\ntext layer; OCR if no\ntext (Tesseract)")
    box(ax, 8.3, 1.2, 3.0, 2.0, "Agent A3", "co-ops & schemes\nBeautifulSoup")
    box(ax, 12.2, 3.4, 2.6, 2.6, "Normalizer", "deterministic:\nLGD codes, crop\nnames, units,\ndedup, checks", AQUA)
    box(ax, 15.3, 5.2, 2.4, 2.4, "SQLite KB", "TELL: rows +\n6 provenance\ncolumns", AQUA)
    box(ax, 15.3, 1.4, 2.4, 2.6, "Query engine", "ASK: keywords +\naliases ->\nparameterised SQL\n+ provenance", AQUA)
    arrow(ax, (3.5, 4.7), (4.4, 4.7))
    for y in (7.1, 4.7, 2.2):
        arrow(ax, (7.4, 4.7), (8.3, y))
        arrow(ax, (11.3, y), (12.2, 4.7))
    arrow(ax, (14.8, 4.9), (15.3, 6.2))
    arrow(ax, (16.5, 5.2), (16.5, 4.0))
    ax.text(0.3, 8.5, "Team 35 Puducherry agricultural information system - Phase 3 architecture",
            fontsize=18, color=INK)
    ax.text(0.3, 0.4, "Routing, normalisation and validation are rule-based (no LLM). Cases the rules "
            "cannot settle are logged with needs_llm_review = 1 (RQ2: QLoRA extractor).",
            fontsize=11, color=INK_2)
    save(fig, "fig_architecture.png")


# ----------------------------------------------------------------------------- figure 4
PROVENANCE = {"source_id", "source_file_or_url", "page_or_table", "agent_id", "run_id", "extracted_at"}


def parse_schema():
    """Read db/schema.sql and return {table: (columns, unique_columns, primary_key)}.
    A simple regex over the CREATE TABLE blocks is enough for this schema."""
    text = (PROJECT / "db" / "schema.sql").read_text(encoding="utf-8")
    tables = {}
    for name, body in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", text, re.S):
        cols, unique, pk = [], [], None
        for line in body.splitlines():
            line = line.strip()
            m = re.match(r"UNIQUE \((.*?)\)", line)
            if m:
                unique = [c.strip() for c in m.group(1).split(",")]
            elif re.match(r"[a-z_0-9]+\s+(INTEGER|TEXT|REAL)", line):
                cols.append(line.split()[0])
                if "PRIMARY KEY" in line:
                    pk = cols[-1]
        tables[name] = (cols, unique, pk)
    return tables


def table_lines(cols, unique, pk):
    """Choose the lines shown in a table box: PK, natural key (UK), link columns (FK) and a
    single provenance note; at most 8 column lines so the boxes stay readable."""
    shown = []
    for c in cols:
        if c in PROVENANCE and c != "run_id":
            continue
        if c == pk:
            shown.append(f"PK {c}")
        elif c in unique:
            shown.append(f"UK {c}")
        elif c.startswith("lgd_") and c != "lgd_state_code":
            shown.append(f"FK {c}")
        elif c == "run_id" and "attempts" in cols:          # pipeline_runs: run_id is the shared key
            shown.append(f"IX {c}")
    shown = shown[:8]
    if PROVENANCE <= set(cols):
        shown.append("+ 6 provenance cols (run_id FK)")
    return shown


ER_PLACE = {"pipeline_runs": (0.3, 12.0), "extraction_issues": (0.3, 7.0),
            "lgd_locations": (7.0, 12.0), "location_aliases": (7.0, 7.0),
            "crop_statistics": (14.2, 12.0), "coop_societies": (14.2, 7.2),
            "market_prices": (20.6, 12.0), "schemes": (20.6, 8.4), "agromet_advisories": (20.6, 5.0)}
ER_WIDTH = 5.6


def draw_table(ax, name, x, top, cols, unique, pk):
    """Draw one table box hanging down from (x, top); return its (left, right, top, bottom) edges."""
    lines = table_lines(cols, unique, pk)
    h = 0.6 + 0.38 * len(lines)
    color = ORANGE if name in ("pipeline_runs", "extraction_issues") else (
        AQUA if name in ("lgd_locations", "location_aliases") else BLUE)
    ax.add_patch(FancyBboxPatch((x, top - h), ER_WIDTH, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                facecolor="white", edgecolor=color, linewidth=2.5))
    ax.text(x + 0.15, top - 0.15, f"{name}  ({len(cols)} cols)", va="top", fontsize=13,
            weight="bold", color=INK)
    for i, line in enumerate(lines):
        ax.text(x + 0.25, top - 0.62 - 0.38 * i, line, va="top", fontsize=10.5, color=INK_2,
                family="monospace")
    return x, x + ER_WIDTH, top, top - h


def link(ax, start, end, label=""):
    """Draw a relationship arrow (from the referencing table to the referenced one)."""
    ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-|>", color=INK_2, lw=1.8))
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.15, label, ha="center",
                fontsize=10, color=INK_2)


def fig_er_diagram():
    """Draw every schema table as a box and the logical links between them."""
    tables = parse_schema()
    fig, ax = plt.subplots(figsize=(24, 13.5))
    ax.set_xlim(0, 26.5)
    ax.set_ylim(0, 13.5)
    ax.axis("off")
    edge = {name: draw_table(ax, name, x, top, *tables[name]) for name, (x, top) in ER_PLACE.items()}
    lgd_left, lgd_right, lgd_top, lgd_bottom = edge["lgd_locations"]
    lgd_mid = (lgd_top + lgd_bottom) / 2
    runs_bottom = edge["pipeline_runs"][3]
    link(ax, (2.0, edge["extraction_issues"][2]), (2.0, runs_bottom), "run_id")
    link(ax, (9.0, edge["location_aliases"][2]), (9.0, lgd_bottom), "canonical_name / lgd codes")
    for name in ("crop_statistics", "coop_societies"):
        left, _r, top, bottom = edge[name]
        link(ax, (left, (top + bottom) / 2), (lgd_right, lgd_mid))
    ag_left = edge["agromet_advisories"][0]
    path_y = edge["coop_societies"][3] - 0.4              # run under the coop_societies box
    ax.plot([ag_left, 13.4, 13.4], [path_y, path_y, lgd_bottom + 0.4], color=INK_2, lw=1.8)
    link(ax, (13.4, lgd_bottom + 0.4), (lgd_right, lgd_bottom + 0.4))
    ax.text(lgd_right + 0.15, lgd_top + 0.1, "FK lgd_district_code /\nlgd_subdistrict_code", fontsize=10,
            color=INK_2, va="bottom")
    ax.text(0.3, 13.1, "Entity-relationship diagram of db/schema.sql (SQLite, 9 tables)", fontsize=18, color=INK)
    ax.text(0.3, 12.65, "PK primary key - IX indexed key - UK part of the UNIQUE natural key (dedup rule) - FK logical link "
            "(documented in schema.sql, not enforced by SQLite).", fontsize=11, color=INK_2)
    ax.text(0.3, 0.5, "Every data table also carries the 6 provenance columns source_id, source_file_or_url, "
            "page_or_table, agent_id, run_id (-> pipeline_runs.run_id), extracted_at.", fontsize=11, color=INK_2)
    save(fig, "fig_er_diagram.png")


# ----------------------------------------------------------------------------- figure 5
def fig_qlora_base_vs_adapter():
    """Base model vs QLoRA adapter F1 on the 16 held-out S3 cases: overall, OCR pages, text layer.
    Numbers come from eval/adapter_comparison.csv and eval/qlora_train_log.json (Colab T4 run)."""
    rows = {r["case_or_subset"]: r for r in read_csv(PROJECT / "eval" / "adapter_comparison.csv")
            if r["row_type"] == "summary"}
    log = json.loads((PROJECT / "eval" / "qlora_train_log.json").read_text(encoding="utf-8"))
    pipeline = next(r for r in read_csv(PROJECT / "eval" / "results_by_agent.csv") if r["agent"] == "A2")
    groups = [("Overall", rows["all"]), ("OCR pages", rows["ocr_tesseract"]),
              ("Text layer", rows["text_layer"])]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    width = 0.34
    for g, (name, r) in enumerate(groups):
        base, adapter = float(r["base_f1"]), float(r["adapter_f1"])
        ax.bar(g - width / 2 - 0.01, base, width, color=ORANGE, label="Base model" if g == 0 else None)
        ax.bar(g + width / 2 + 0.01, adapter, width, color=BLUE, label="QLoRA adapter" if g == 0 else None)
        ax.text(g - width / 2 - 0.01, base + 0.015, f"{base:.4f}", ha="center", va="bottom", fontsize=12, color=INK)
        ax.text(g + width / 2 + 0.01, adapter + 0.015, f"{adapter:.4f}", ha="center", va="bottom",
                fontsize=12, color=INK)
        ax.text(g, max(base, adapter) + 0.11, f"ΔF1 = {float(r['delta_f1']):+.4f}", ha="center",
                va="bottom", fontsize=13, fontweight="bold", color=INK)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([f"{name}\nn={r['n_cases']} cases, {r['n_fields']} fields" for name, r in groups])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Field-level F1")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    ax.set_title(f"{log['base_model'].split('/')[-1]}: base vs 4-bit QLoRA adapter on held-out S3 table "
                 "columns", loc="left")
    fig.text(0.01, -0.03, f"Adapter: r={log['r']}, alpha={log['lora_alpha']}, {log['epochs']} epochs, "
             f"{log['train_examples']} training examples (2020-21, 2022-23, 2023-24; zero overlap with "
             f"the test cases), {log['gpu']}, {log['train_seconds']:.0f} s.", fontsize=10, color=INK_2)
    o = rows["all"]
    fig.text(0.01, -0.07, f"Overall P/R: base {float(o['base_precision']):.4f}/{float(o['base_recall']):.4f}, "
             f"adapter {float(o['adapter_precision']):.4f}/{float(o['adapter_recall']):.4f}. The deterministic "
             f"A2 parser scores F1 = {float(pipeline['f1']):.3f} on the same 16 cases.", fontsize=10, color=INK_2)
    save(fig, "fig_qlora_base_vs_adapter.png")


def save(fig, name):
    """Save a figure at 300 dpi with a white background and close it."""
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote docs/figures/{name}")


if __name__ == "__main__":
    fig_extraction_f1()
    fig_crop_trends()
    fig_architecture()
    fig_er_diagram()
    fig_qlora_base_vs_adapter()
