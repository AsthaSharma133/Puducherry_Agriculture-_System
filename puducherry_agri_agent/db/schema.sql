-- Phase 3 schema: Puducherry Agricultural Intelligence System (Team 35)
-- Dialect: SQLite 3 (db/puducherry_agri.db). Applied by src/common/db.py.
--
-- Provenance contract: every DATA table carries the same six columns
--   source_id           manifest id (S2, S3, S5, S6, S7, S8)
--   source_file_or_url  local raw file path (relative to puducherry_agri_agent/) or URL
--   page_or_table       where in the source the value came from (e.g. "p50 Table V-B col (13)")
--   agent_id            A1 / A2 / A3 / REF (non-agent lookup loader)
--   run_id              FK -> pipeline_runs.run_id (the run that wrote the row)
--   extracted_at        ISO-8601 timestamp of extraction
-- Re-running a source deletes that source's rows first, so tables never hold stale duplicates.

PRAGMA foreign_keys = ON;

-- --------------------------------------------------------------------------
-- Provenance & automation log (one row per source step, plus one 'ALL' row per run)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_step_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,              -- e.g. 20261126T193000Z-ab12cd
    source_id       TEXT NOT NULL,              -- S1..S9 or 'ALL'
    agent_id        TEXT,                       -- A1 / A2 / A3 / REF / ORCH
    status          TEXT NOT NULL CHECK (status IN
                        ('SUCCESS', 'PARTIAL', 'FAILED', 'PENDING', 'SKIPPED')),
    attempts        INTEGER NOT NULL DEFAULT 1,
    inputs_found    INTEGER,                    -- raw files / pages available to the agent
    records_out     INTEGER,                    -- rows written to data tables
    issues_logged   INTEGER,                    -- rows written to extraction_issues
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    duration_s      REAL,
    error_message   TEXT,
    notes           TEXT,
    trace_backend   TEXT                        -- 'langsmith' or 'none'
);
CREATE INDEX IF NOT EXISTS ix_runs_run ON pipeline_runs(run_id);

-- Every parse/validation problem the agents hit (feeds the User Manual troubleshooting section)
CREATE TABLE IF NOT EXISTS extraction_issues (
    issue_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    severity            TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
    issue_type          TEXT NOT NULL,          -- e.g. no_text_layer, state_sum_mismatch, unmapped_header
    detail              TEXT NOT NULL,
    needs_llm_review    INTEGER NOT NULL DEFAULT 0 CHECK (needs_llm_review IN (0, 1)),
    source_id           TEXT NOT NULL,
    source_file_or_url  TEXT,
    page_or_table       TEXT,
    agent_id            TEXT,
    run_id              TEXT NOT NULL,
    extracted_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_issues_source ON extraction_issues(source_id, issue_type);

-- --------------------------------------------------------------------------
-- S7: LGD administrative units (state, districts, sub-districts, villages) + 4 reporting regions
CREATE TABLE IF NOT EXISTS lgd_locations (
    location_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type             TEXT NOT NULL CHECK (entity_type IN
                                ('state', 'district', 'subdistrict', 'village', 'region')),
    lgd_code                INTEGER,             -- NULL for 'region' (not an LGD unit)
    name                    TEXT NOT NULL,
    local_name              TEXT,                -- Tamil / Malayalam / Telugu as published by LGD
    lgd_state_code          INTEGER NOT NULL DEFAULT 34,
    lgd_district_code       INTEGER,
    lgd_subdistrict_code    INTEGER,
    region                  TEXT CHECK (region IN ('Puducherry', 'Karaikal', 'Mahe', 'Yanam')),
    census2011_code         TEXT,
    status                  TEXT,                -- LGD village status (e.g. Inhabitant)
    source_id           TEXT NOT NULL,
    source_file_or_url  TEXT NOT NULL,
    page_or_table       TEXT,
    agent_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    extracted_at        TEXT NOT NULL,
    UNIQUE (entity_type, lgd_code, name)
);

-- Spelling aliases from data/aliases.csv (Pondicherry -> Puducherry, KKL -> Karaikal, ...)
CREATE TABLE IF NOT EXISTS location_aliases (
    alias                   TEXT NOT NULL,
    alias_key               TEXT NOT NULL,       -- casefolded, punctuation-stripped lookup key
    canonical_name          TEXT NOT NULL,
    entity_type             TEXT NOT NULL,
    lgd_district_code       INTEGER,
    lgd_subdistrict_code    INTEGER,
    notes                   TEXT,
    source_id           TEXT NOT NULL,
    source_file_or_url  TEXT NOT NULL,
    page_or_table       TEXT,
    agent_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    extracted_at        TEXT NOT NULL,
    UNIQUE (alias_key, entity_type, canonical_name)
);

-- --------------------------------------------------------------------------
-- S3: region-wise crop statistics (Season & Crop Report Tables IV-A area, V-A yield, V-B out-turn)
CREATE TABLE IF NOT EXISTS crop_statistics (
    stat_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_year               TEXT NOT NULL,       -- agricultural year July-June, e.g. 2020-21
    region                  TEXT NOT NULL CHECK (region IN
                                ('Puducherry', 'Karaikal', 'Mahe', 'Yanam', 'UT')),
    lgd_district_code       INTEGER,             -- 598 Karaikal / 600 Puducherry (incl. Mahe, Yanam)
    lgd_subdistrict_code    INTEGER,             -- 5913 Mahe / 5908 Yanam; NULL otherwise
    crop                    TEXT NOT NULL,       -- canonical name (src/normalizer/crops.py)
    season                  TEXT NOT NULL DEFAULT 'All' CHECK (season IN ('I', 'II', 'III', 'All')),
    is_aggregate            INTEGER NOT NULL DEFAULT 0 CHECK (is_aggregate IN (0, 1)),
    crop_label_raw          TEXT,                -- header text as printed in the PDF
    area_ha                 REAL CHECK (area_ha IS NULL OR area_ha >= 0),
    yield_value             REAL CHECK (yield_value IS NULL OR yield_value >= 0),
    yield_unit              TEXT,                -- kg/ha, nuts/ha
    production_value        REAL CHECK (production_value IS NULL OR production_value >= 0),
    production_unit         TEXT,                -- tonnes, thousand nuts
    product_form            TEXT,                -- e.g. 'rice (milled)', 'kapas', 'kernels'
    extraction_method       TEXT NOT NULL,       -- text_layer | ocr_tesseract
    header_source           TEXT NOT NULL,       -- 'page' or 'template:<year>' for OCR pages
    validation_status       TEXT NOT NULL,       -- ok | state_sum_mismatch | area_yield_mismatch | ...
    area_yield_rel_error    REAL,                -- |area*yield/1000 - production| / production
    source_id           TEXT NOT NULL,
    source_file_or_url  TEXT NOT NULL,
    page_or_table       TEXT NOT NULL,
    agent_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    extracted_at        TEXT NOT NULL,
    UNIQUE (crop_year, region, crop, season)
);
CREATE INDEX IF NOT EXISTS ix_crop_year ON crop_statistics(crop_year, crop);

-- --------------------------------------------------------------------------
-- S6: credit co-operative societies (entity list only: no warehouse/capacity data exists)
CREATE TABLE IF NOT EXISTS coop_societies (
    society_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    region                  TEXT NOT NULL CHECK (region IN ('Puducherry', 'Karaikal', 'Mahe', 'Yanam')),
    region_raw              TEXT,                -- as printed ('Pondy')
    lgd_district_code       INTEGER,
    lgd_subdistrict_code    INTEGER,
    society_type            TEXT,                -- Primary / Central / Apex
    reg_no                  TEXT NOT NULL,
    name                    TEXT NOT NULL,
    status                  TEXT NOT NULL CHECK (status IN ('working', 'dormant')),
    source_id           TEXT NOT NULL,
    source_file_or_url  TEXT NOT NULL,
    page_or_table       TEXT NOT NULL,
    agent_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    extracted_at        TEXT NOT NULL,
    UNIQUE (reg_no, name)
);

-- --------------------------------------------------------------------------
-- S2 (schema ready): UT-level average wholesale prices, one row per commodity x year
CREATE TABLE IF NOT EXISTS market_prices (
    price_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    period                  TEXT NOT NULL,       -- e.g. 2013-14 (financial/agri year as printed)
    market_level            TEXT NOT NULL DEFAULT 'UT average wholesale',
    region                  TEXT,                -- NULL = UT level
    commodity               TEXT NOT NULL,
    variety                 TEXT NOT NULL DEFAULT '',
    price_value             REAL CHECK (price_value IS NULL OR price_value > 0),
    price_unit              TEXT NOT NULL,       -- Rs/quintal, Rs/1000 nuts
    unit_raw                TEXT,
    source_id           TEXT NOT NULL,
    source_file_or_url  TEXT NOT NULL,
    page_or_table       TEXT NOT NULL,
    agent_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    extracted_at        TEXT NOT NULL,
    UNIQUE (period, market_level, region, commodity, variety)
);

-- --------------------------------------------------------------------------
-- S5 (schema ready): scheme incentives
CREATE TABLE IF NOT EXISTS schemes (
    scheme_row_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_name             TEXT NOT NULL,
    category                TEXT,                -- section heading on the page
    crop                    TEXT,
    assistance_amount_rs    REAL,
    amount_basis            TEXT,                -- per acre / per ha / per unit / lump sum
    period_basis            TEXT,                -- per season / per year / one-time
    description             TEXT,
    valid_from              TEXT,                -- page is undated: access date is recorded
    source_id           TEXT NOT NULL,
    source_file_or_url  TEXT NOT NULL,
    page_or_table       TEXT NOT NULL,
    agent_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    extracted_at        TEXT NOT NULL,
    UNIQUE (scheme_name, crop, description)
);

-- --------------------------------------------------------------------------
-- S8 (schema ready): Agromet Advisory Bulletin values (long format)
CREATE TABLE IF NOT EXISTS agromet_advisories (
    advisory_row_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    bulletin_date           TEXT NOT NULL,       -- ISO date of issue
    region                  TEXT NOT NULL CHECK (region IN ('Puducherry', 'Karaikal')),
    lgd_district_code       INTEGER,
    section                 TEXT NOT NULL CHECK (section IN
                                ('past_weather', 'forecast', 'advisory', 'other')),
    target_date             TEXT,                -- the day a weather value refers to (as printed)
    parameter               TEXT,                -- Rainfall, Tmax, Tmin, RH, Wind speed, ...
    value_text              TEXT,                -- as printed
    value_num               REAL,
    unit                    TEXT,
    crop                    TEXT,                -- for advisory rows
    advisory_text           TEXT,
    source_id           TEXT NOT NULL,
    source_file_or_url  TEXT NOT NULL,
    page_or_table       TEXT NOT NULL,
    agent_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    extracted_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_agromet ON agromet_advisories(bulletin_date, region, section);
