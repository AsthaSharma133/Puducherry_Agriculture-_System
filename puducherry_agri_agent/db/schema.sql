-- Phase 2 Database Schema: Puducherry Agricultural Intelligence Agent (Team 35)
-- Dialect: PostgreSQL / SQLite Compatible

-- 1. Administrative Entity Registry (LGD Normalization)
CREATE TABLE IF NOT EXISTS lgd_administrative_registry (
    lgd_village_code INTEGER PRIMARY KEY,
    village_name VARCHAR(150) NOT NULL,
    lgd_subdistrict_code INTEGER NOT NULL,
    subdistrict_name VARCHAR(100) NOT NULL,
    lgd_district_code INTEGER NOT NULL,
    district_name VARCHAR(100) NOT NULL, -- Puducherry, Karaikal, Mahe, Yanam
    state_code INTEGER DEFAULT 34,
    state_name VARCHAR(50) DEFAULT 'Puducherry',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Subsidies & Schemes Registry
CREATE TABLE IF NOT EXISTS schemes_and_incentives (
    scheme_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_name VARCHAR(255) NOT NULL,
    target_crop VARCHAR(100),
    subsidy_amount_per_acre NUMERIC(10, 2),
    eligibility_criteria TEXT,
    regional_scope VARCHAR(100), -- Puducherry, Karaikal, Mahe, Yanam
    source_url TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Weekly Advisories & Weather
CREATE TABLE IF NOT EXISTS weekly_crop_advisories (
    advisory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE NOT NULL,
    district_name VARCHAR(100) NOT NULL,
    rainfall_mm NUMERIC(6, 2),
    crop_status_summary TEXT,
    pest_warning TEXT,
    advisory_text TEXT,
    source_pdf_url TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Mandi Prices & Arrivals (AGMARKNET Dynamic Data)
CREATE TABLE IF NOT EXISTS mandi_prices_arrivals (
    arrival_id INTEGER PRIMARY KEY AUTOINCREMENT,
    arrival_date DATE NOT NULL,
    district_name VARCHAR(100) NOT NULL,
    market_name VARCHAR(150) NOT NULL,
    commodity_name VARCHAR(100) NOT NULL,
    variety VARCHAR(100),
    arrival_tonnes NUMERIC(10, 2),
    min_price_rs_per_qtl NUMERIC(10, 2),
    max_price_rs_per_qtl NUMERIC(10, 2),
    modal_price_rs_per_qtl NUMERIC(10, 2),
    lgd_village_code INTEGER,
    source_portal VARCHAR(50) DEFAULT 'AGMARKNET',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lgd_village_code) REFERENCES lgd_administrative_registry(lgd_village_code)
);

-- 5. Regulated Market Retail & Wholesale Prices
CREATE TABLE IF NOT EXISTS regulated_market_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    price_date DATE NOT NULL,
    market_location VARCHAR(150) NOT NULL,
    commodity_name VARCHAR(100) NOT NULL,
    retail_price_per_kg NUMERIC(8, 2),
    wholesale_price_per_qtl NUMERIC(10, 2),
    source_url TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Production & Yield Statistics (DES Reports)
CREATE TABLE IF NOT EXISTS crop_production_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_year VARCHAR(20) NOT NULL,
    district_name VARCHAR(100) NOT NULL,
    crop_name VARCHAR(100) NOT NULL,
    area_hectares NUMERIC(10, 2),
    production_metric_tonnes NUMERIC(12, 2),
    yield_kg_per_hectare NUMERIC(10, 2),
    source_pdf_url TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Warehousing & Storage Infrastructure
CREATE TABLE IF NOT EXISTS storage_warehouse_logistics (
    facility_id INTEGER PRIMARY KEY AUTOINCREMENT,
    society_name VARCHAR(255) NOT NULL,
    facility_type VARCHAR(100),
    region_name VARCHAR(100) NOT NULL,
    capacity_metric_tonnes NUMERIC(10, 2),
    contact_details TEXT,
    source_url TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Meta logs table for pipeline execution tracing
CREATE TABLE IF NOT EXISTS scraped_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    status TEXT CHECK (status IN ('SUCCESS', 'FAILED')),
    characters_extracted INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);