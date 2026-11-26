"""Map one crop number per region onto the Survey of India (SOI) district boundaries.
The SOI shapefile needs a manual sign-in download, so this script explains what to do if it
is missing. Output: docs/figures/fig_soi_map.png (300 dpi).

    python scripts/plot_soi_map.py                                   # Paddy production, latest year
    python scripts/plot_soi_map.py --crop Sugarcane --metric area_ha --year 2023-24
    python scripts/plot_soi_map.py --shapefile path/to/districts.shp # use a specific file

The 4 regions are far apart (Puducherry and Karaikal on the east coast, Yanam in Andhra
Pradesh, Mahe in Kerala), so each region is drawn in its own panel with its value.
Attribution: boundaries (c) Survey of India.
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOI_DIR = PROJECT / "data" / "raw" / "soi"
DB_PATH = PROJECT / "db" / "puducherry_agri.db"
OUT = PROJECT / "docs" / "figures" / "fig_soi_map.png"
REGIONS = ["Puducherry", "Karaikal", "Mahe", "Yanam"]
SEQ_BLUE = ["#cce3fd", "#84b9f3", "#338ced", "#1b64be", "#0e3d7e"]   # light -> dark, one hue
INSTRUCTIONS = """
Survey of India shapefile not found in data/raw/soi/.

How to get it (about 10 minutes, free):
  1. Open https://onlinemaps.surveyofindia.gov.in/Digital_Product_Show.aspx and sign in
     (create a free account if needed).
  2. Choose the 'Administrative Boundary Database' product (district level, OVSF/1M/7),
     price Rs 0, and download the zip from the time-limited link.
  3. Unzip it into data/raw/soi/ so that a *.shp file (with its .shx, .dbf, .prj) is there.
  4. Run again:  python scripts/plot_soi_map.py
Credit 'Survey of India' on every map that uses these boundaries (manifest source S9).
"""


def find_shapefile(given):
    """Return the shapefile to use: the --shapefile argument, else the first .shp in data/raw/soi/."""
    if given:
        return Path(given) if Path(given).exists() else None
    files = sorted(SOI_DIR.rglob("*.shp")) if SOI_DIR.exists() else []
    return files[0] if files else None


def region_values(crop, metric, year):
    """Read one crop metric per region from crop_statistics, plus the page it came from.
    Returns (year used, {region: (value, page_or_table)})."""
    conn = sqlite3.connect(DB_PATH)
    if year is None:
        year = conn.execute("SELECT MAX(crop_year) FROM crop_statistics").fetchone()[0]
    rows = conn.execute(f"SELECT region, {metric}, page_or_table FROM crop_statistics WHERE crop = ? "
                        f"AND season = 'All' AND crop_year = ?", (crop, year)).fetchall()
    conn.close()
    return year, {r[0]: (r[1], r[2]) for r in rows if r[0] in REGIONS}


def alias_lookup():
    """Return {normalised alias: canonical region} from the location_aliases table."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT alias_key, canonical_name FROM location_aliases "
                        "WHERE entity_type = 'region'").fetchall()
    conn.close()
    return dict(rows)


def match_regions(gdf, aliases):
    """Find the shapefile column whose values are region names and add a 'region' column.
    Names are normalised the same way as location_aliases ('PONDICHERRY' -> Puducherry)."""
    def norm(value):
        return re.sub(r"[^a-z]", "", str(value).lower())

    best_col, best_hits = None, 0
    for col in gdf.columns:
        if col == "geometry":
            continue
        hits = sum(norm(v) in aliases for v in gdf[col].astype(str))
        if hits > best_hits:
            best_col, best_hits = col, hits
    if best_col is None:
        return None
    gdf["region"] = [aliases.get(norm(v)) for v in gdf[best_col].astype(str)]
    return gdf[gdf["region"].isin(REGIONS)].dissolve(by="region").reset_index()


def color_for(value, top):
    """Pick a step of the sequential blue ramp for a value (0 gets the lightest step)."""
    if not top:
        return SEQ_BLUE[0]
    return SEQ_BLUE[min(int(value / top * (len(SEQ_BLUE) - 1) + 0.5), len(SEQ_BLUE) - 1)]


def draw(regions_gdf, values, crop, metric, year):
    """Draw the 4 regions in a 2x2 grid, each filled by its value and labelled with it."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    unit = {"area_ha": "ha", "yield_value": "kg/ha", "production_value": "tonnes"}[metric]
    top = max((v for v, _p in values.values() if v), default=0)
    fig, axes = plt.subplots(2, 2, figsize=(12, 11))
    for ax, region in zip(axes.flat, REGIONS):
        value, page = values.get(region, (None, ""))
        shape = regions_gdf[regions_gdf["region"] == region]
        ax.set_axis_off()
        if shape.empty:
            ax.set_title(f"{region}: not in shapefile", fontsize=14)
            continue
        shape.plot(ax=ax, color=color_for(value or 0, top), edgecolor="#191919", linewidth=1)
        label = "no data" if value is None else f"{value:,.0f} {unit}"
        ax.set_title(f"{region}\n{label}", fontsize=16)
        ax.text(0.5, -0.04, page.split(";")[0], transform=ax.transAxes, ha="center", fontsize=9,
                color="#666666")
    fig.suptitle(f"{crop} {metric.replace('_value', '').replace('_ha', ' area')} by region, {year}",
                 fontsize=18, x=0.02, ha="left")
    fig.text(0.02, 0.01, "Boundaries: (c) Survey of India (S9). Values: S3 Season & Crop Report via "
             "db/puducherry_agri.db. Panels are not to a common scale.", fontsize=10, color="#666666")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT.relative_to(PROJECT)}")


def main(argv=None):
    """Check inputs, join DB values onto the SOI districts and draw the map."""
    ap = argparse.ArgumentParser(description="Plot region crop values on the SOI district map")
    ap.add_argument("--crop", default="Paddy")
    ap.add_argument("--metric", default="production_value",
                    choices=["area_ha", "yield_value", "production_value"])
    ap.add_argument("--year", default=None, help="e.g. 2023-24 (default: latest)")
    ap.add_argument("--shapefile", default=None)
    args = ap.parse_args(argv)
    shp = find_shapefile(args.shapefile)
    if shp is None:
        print(INSTRUCTIONS)
        return 0
    try:
        import geopandas
    except ImportError:
        print("geopandas is not installed: pip install geopandas   (then run this script again)")
        return 1
    regions_gdf = match_regions(geopandas.read_file(shp), alias_lookup())
    if regions_gdf is None or regions_gdf.empty:
        print(f"No Puducherry region names found in {shp.name}; check its attribute columns.")
        return 1
    year, values = region_values(args.crop, args.metric, args.year)
    draw(regions_gdf, values, args.crop, args.metric, year)
    return 0


if __name__ == "__main__":
    sys.exit(main())
