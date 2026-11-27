"""Map real crop numbers from the SQLite KB onto Survey of India (SOI) district boundaries.
Output: docs/figures/fig_puducherry_soi_map.png (300 dpi).

    python scripts/plot_soi_map.py                                   # Paddy, latest year
    python scripts/plot_soi_map.py --crop Sugarcane --year 2023-24
    python scripts/plot_soi_map.py --shapefile path/to/districts.shp # use a specific file

Boundary source (manifest S9): Survey of India index maps, 2011 Census districts, as digitised
by the DataMeet India community: https://github.com/datameet/maps
(Survey-of-India-Index-Maps/Boundaries/India-Districts-2011Census.*, India-States.*), CC BY 4.0.
The official SOI portal download was not available, so this SOI-derived mirror is used.
Download the 8 files into data/raw/soi/ (git-ignored, ~16 MB):
    python scripts/plot_soi_map.py --download

The 4 regions are far apart (Puducherry and Karaikal on the Tamil Nadu coast, Yanam in Andhra
Pradesh, Mahe in Kerala), so the figure has a locator map plus one zoomed panel per region.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOI_DIR = PROJECT / "data" / "raw" / "soi"
DB_PATH = PROJECT / "db" / "puducherry_agri.db"
OUT = PROJECT / "docs" / "figures" / "fig_puducherry_soi_map.png"
MIRROR = "https://raw.githubusercontent.com/datameet/maps/master/Survey-of-India-Index-Maps/Boundaries/"
LAYERS = ["India-Districts-2011Census", "India-States"]
DISTRICTS = SOI_DIR / "India-Districts-2011Census.shp"
STATES = SOI_DIR / "India-States.shp"
REGIONS = ["Puducherry", "Karaikal", "Mahe", "Yanam"]
SECOND_CROP = "Coconut"                      # the one crop grown in all 4 regions
SEQ_BLUE = ["#cce3fd", "#84b9f3", "#338ced", "#1b64be", "#0e3d7e"]   # light -> dark, one hue
ZERO_FILL = "#ececec"                        # region where the crop is not grown
INK, INK_2, LAND, EDGE = "#191919", "#5c5c5c", "#f2f0eb", "#ffffff"
ATTRIBUTION = ("Boundaries: Survey of India index maps (2011 Census districts), digitised by the "
               "DataMeet India community, github.com/datameet/maps (CC BY 4.0).")

# Locator map: where each region's callout text sits (lon, lat) - all in the sea, away from land
CALLOUT = {"Yanam": (83.3, 15.5), "Puducherry": (81.2, 12.9), "Karaikal": (81.2, 10.2),
           "Mahe": (74.2, 10.4)}
STATE_LABELS = {"Tamil Nadu": (78.2, 11.0), "Kerala": (76.35, 9.6), "Karnataka": (76.0, 14.6),
                "Andhra Pradesh": (79.4, 15.6), "Telangana": (78.9, 17.9)}
LOCATOR_BOX = (73.8, 84.6, 7.9, 19.2)        # lon min, lon max, lat min, lat max


def download():
    """Fetch the 8 SOI-derived boundary files from the DataMeet mirror into data/raw/soi/."""
    import requests

    SOI_DIR.mkdir(parents=True, exist_ok=True)
    for layer in LAYERS:
        for ext in ("shp", "shx", "dbf", "prj"):
            name = f"{layer}.{ext}"
            r = requests.get(MIRROR + name, timeout=180)
            r.raise_for_status()
            (SOI_DIR / name).write_bytes(r.content)
            print(f"  {name}: {len(r.content):,} bytes")


def crop_values(crop, year):
    """Read area, yield and production of one crop for each region from crop_statistics.
    Returns {region: dict(area, yield, yield_unit, production, production_unit, page)}."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT region, area_ha, yield_value, yield_unit, production_value, "
                        "production_unit, page_or_table FROM crop_statistics WHERE crop = ? "
                        "AND season = 'All' AND crop_year = ?", (crop, year)).fetchall()
    conn.close()
    keys = ["area", "yield", "yield_unit", "production", "production_unit", "page"]
    return {r[0]: dict(zip(keys, r[1:])) for r in rows if r[0] in REGIONS}


def latest_year():
    conn = sqlite3.connect(DB_PATH)
    year = conn.execute("SELECT MAX(crop_year) FROM crop_statistics").fetchone()[0]
    conn.close()
    return year


def fill_color(value, top):
    """Sequential blue step for a value; grey when the crop is not grown (0 or missing)."""
    if not value or not top:
        return ZERO_FILL
    return SEQ_BLUE[min(int(value / top * len(SEQ_BLUE)), len(SEQ_BLUE) - 1)]


def nice_km(width_km):
    """A round scale-bar length of about a quarter of the panel width."""
    for km in (0.5, 1, 2, 5, 10, 20, 50):
        if km >= width_km / 4:
            return km
    return 50


def draw_locator(ax, states, regions):
    """South India with the 4 regions marked and labelled by callouts placed in the sea."""
    x0, x1, y0, y1 = LOCATOR_BOX
    states.plot(ax=ax, color=LAND, edgecolor="#c9c6bf", linewidth=0.6)
    regions.plot(ax=ax, color=SEQ_BLUE[4], edgecolor=SEQ_BLUE[4], linewidth=1.5)
    for name, (lx, ly) in STATE_LABELS.items():
        ax.text(lx, ly, name, ha="center", va="center", fontsize=9, color="#9a968e", style="italic")
    for _, row in regions.iterrows():
        p = row.geometry.representative_point()
        ax.plot(p.x, p.y, "o", ms=11, mfc="none", mec=SEQ_BLUE[4], mew=1.6)
        tx, ty = CALLOUT[row["region"]]
        ax.annotate(row["region"], (p.x, p.y), (tx, ty), fontsize=12, fontweight="bold", color=INK,
                    ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", color=INK_2, lw=0.8, shrinkB=7))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_facecolor("#eef5fc")             # sea
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")                       # geopandas adds CRS axis labels; not needed here
    ax.set_ylabel("")
    for spine in ax.spines.values():
        spine.set_color("#c9c6bf")
    ax.set_title("Puducherry UT: 4 separate regions", fontsize=14, loc="left", color=INK)


def draw_region(ax, shape, region, main, second, crop, top):
    """One zoomed panel: the region filled by the main crop's production, numbers underneath."""
    import math

    shape.plot(ax=ax, color=fill_color(main.get("production"), top), edgecolor=INK, linewidth=0.9)
    minx, miny, maxx, maxy = shape.total_bounds
    pad_x, pad_y = (maxx - minx) * 0.12, (maxy - miny) * 0.12
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    # true shape at this latitude; 'datalim' keeps every panel box the same size
    ax.set_aspect(1 / math.cos(math.radians((miny + maxy) / 2)), adjustable="datalim")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for spine in ax.spines.values():
        spine.set_color("#d6d6d6")
    # scale bar in the lower-left corner
    km_per_deg = 111.32 * math.cos(math.radians((miny + maxy) / 2))
    width_km = (maxx - minx + 2 * pad_x) * km_per_deg
    km = nice_km(width_km)
    bx, by = minx - pad_x * 0.6, miny - pad_y * 0.8
    ax.plot([bx, bx + km / km_per_deg], [by, by], color=INK, lw=2.2, solid_capstyle="butt")
    ax.text(bx + km / km_per_deg / 2, by + pad_y * 0.1, f"{km:g} km", ha="center", va="bottom",
            fontsize=8, color=INK)
    ax.set_title(region, fontsize=14, fontweight="bold", loc="left", color=INK)
    if main.get("production"):
        line1 = (f"{crop}: {main['production']:,.0f} {main['production_unit']}  ·  "
                 f"{main['yield']:,.0f} {main['yield_unit']}")
    else:
        line1 = f"{crop}: not grown (0 ha)"
    line2 = (f"{SECOND_CROP}: {second['area']:,.0f} ha  ·  "
             f"{second['production']:,.0f} {second['production_unit']}")
    ax.text(0.0, -0.04, line1 + "\n" + line2, transform=ax.transAxes, ha="left", va="top",
            fontsize=10, color=INK, linespacing=1.5)


def main(argv=None):
    """Load boundaries, join the KB values by region name and draw the figure."""
    ap = argparse.ArgumentParser(description="Plot crop values on Survey of India boundaries")
    ap.add_argument("--crop", default="Paddy")
    ap.add_argument("--year", default=None, help="e.g. 2023-24 (default: latest)")
    ap.add_argument("--shapefile", default=None, help="district shapefile (default: data/raw/soi/)")
    ap.add_argument("--download", action="store_true", help="download the SOI-derived files first")
    args = ap.parse_args(argv)
    if args.download:
        download()
    districts_shp = Path(args.shapefile) if args.shapefile else DISTRICTS
    if not districts_shp.exists() or not STATES.exists():
        print(f"Boundary files missing in {SOI_DIR.relative_to(PROJECT)}/ - run: "
              f"python scripts/plot_soi_map.py --download")
        return 1
    try:
        import geopandas
        import matplotlib
    except ImportError:
        print("geopandas is not installed: pip install geopandas   (then run this script again)")
        return 1
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    districts = geopandas.read_file(districts_shp)
    regions = districts[(districts["ST_NM"] == "Puducherry") & districts["DISTRICT"].isin(REGIONS)]
    regions = regions.rename(columns={"DISTRICT": "region"})
    missing = set(REGIONS) - set(regions["region"])
    if missing:
        print(f"Regions not found in {districts_shp.name}: {sorted(missing)}")
        return 1
    x0, x1, y0, y1 = LOCATOR_BOX
    states = geopandas.read_file(STATES).clip((x0 - 1, y0 - 1, x1 + 1, y1 + 1))

    year = args.year or latest_year()
    main_vals, second_vals = crop_values(args.crop, year), crop_values(SECOND_CROP, year)
    top = max((v["production"] or 0) for v in main_vals.values())

    fig = plt.figure(figsize=(16, 10))
    grid = fig.add_gridspec(2, 3, width_ratios=[1.3, 1, 1], wspace=0.12, hspace=0.42)
    draw_locator(fig.add_subplot(grid[:, 0]), states, regions)
    for i, region in enumerate(REGIONS):
        ax = fig.add_subplot(grid[i // 2, 1 + i % 2])
        draw_region(ax, regions[regions["region"] == region], region, main_vals.get(region, {}),
                    second_vals[region], args.crop, top)

    step = top / len(SEQ_BLUE)
    handles = [Patch(color=ZERO_FILL, label="not grown")] + [
        Patch(color=c, label=f"{i * step:,.0f}–{(i + 1) * step:,.0f}") for i, c in enumerate(SEQ_BLUE)]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.38, 0.03), ncol=6,
               frameon=False, fontsize=9, title=f"Region fill: {args.crop} production {year} (tonnes)",
               title_fontsize=10)
    fig.suptitle(f"{args.crop} and {SECOND_CROP} in the four regions of Puducherry, {year}",
                 fontsize=18, x=0.125, ha="left", y=0.98, color=INK)
    fig.text(0.125, -0.045, f"Values: S3 Season & Crop Report {year} (Tables IV-A, V-A, V-B) via "
             "db/puducherry_agri.db. Region panels are zoomed to different scales (see km bars).",
             fontsize=9, color=INK_2)
    fig.text(0.125, -0.07, ATTRIBUTION, fontsize=9, color=INK_2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT.relative_to(PROJECT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
