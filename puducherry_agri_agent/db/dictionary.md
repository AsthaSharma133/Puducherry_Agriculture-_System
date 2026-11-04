# Database Dictionary — Puducherry Agricultural Intelligence System

This data dictionary documents the database tables, column definitions, data types, constraints, and relationships for the Puducherry Agricultural Intelligence Agent (Team 35).


## 1. Table: `lgd_administrative_registry`

* **`lgd_village_code`**: Primary Key, Integer.
* **`village_name`**: Text (150). Standardized village name.
* **`lgd_subdistrict_code`**: Integer. LGD code for the sub-district / taluk.
* **`subdistrict_name`**: Text (100). Name of the sub-district / taluk.
* **`lgd_district_code`**: Integer. LGD code for the district.
* **`district_name`**: Text (100). District jurisdiction (`Puducherry`, `Karaikal`, `Mahe`, `Yanam`).
* **`state_code`**: Integer. LGD State Code (Default `34` for Puducherry UT).
* **`state_name`**: Text (50). State name (Default `Puducherry`).
* **`created_at`**: Timestamp. Record insertion timestamp.

---

## 2. Table: `schemes_and_incentives`

* **`scheme_id`**: Primary Key, Auto-incrementing Integer. Unique scheme record ID.
* **`scheme_name`**: Text (255), Not Null. Name of the subsidy or scheme.
* **`target_crop`**: Text (100). Eligible crops (e.g., `Paddy`, `Pulses`, `Groundnut`).
* **`subsidy_amount_per_acre`**: Decimal (10,2). Financial incentive value in INR per acre.
* **`eligibility_criteria`**: Text. Requirements for farmer eligibility.
* **`regional_scope`**: Text (100). Enclave scope (`Puducherry`, `Karaikal`, `Mahe`, `Yanam`, or `UT Wide`).
* **`source_url`**: Text. Source URL endpoint (`https://agri.py.gov.in/schemes.html`).
* **`ingested_at`**: Timestamp. Data ingestion timestamp.

---

## 3. Table: `weekly_crop_advisories`

* **`advisory_id`**: Primary Key, Auto-incrementing Integer. Unique advisory record ID.
* **`report_date`**: Date, Not Null. Date of advisory publication (`YYYY-MM-DD`).
* **`district_name`**: Text (100), Not Null. Target district name.
* **`rainfall_mm`**: Decimal (6,2). Recorded weekly rainfall in millimeters.
* **`crop_status_summary`**: Text. Summary of crop status and seasonal conditions.
* **`pest_warning`**: Text. Pest alerts and recommended chemical/organic interventions.
* **`advisory_text`**: Text. Full extracted advisory narrative.
* **`source_pdf_url`**: Text. Source PDF publication URL.
* **`ingested_at`**: Timestamp. Data ingestion timestamp.

---

## 4. Table: `mandi_prices_arrivals`

* **`arrival_id`**: Primary Key, Auto-incrementing Integer. Unique arrival transaction ID.
* **`arrival_date`**: Date, Not Null. Date of market trade (`YYYY-MM-DD`).
* **`district_name`**: Text (100), Not Null. District market location.
* **`market_name`**: Text (150), Not Null. Regulated mandi / market yard name.
* **`commodity_name`**: Text (100), Not Null. Commodity traded (e.g., `Paddy (Dhan)`, `Cotton`).
* **`variety`**: Text (100). Crop variety classification.
* **`arrival_tonnes`**: Decimal (10,2). Tonnage arrived at market yard.
* **`min_price_rs_per_qtl`**: Decimal (10,2). Minimum trade price per quintal (100 kg).
* **`max_price_rs_per_qtl`**: Decimal (10,2). Maximum trade price per quintal.
* **`modal_price_rs_per_qtl`**: Decimal (10,2). Modal / average trade price per quintal.
* **`lgd_village_code`**: Foreign Key (Integer). Links market location to `lgd_administrative_registry`.
* **`source_portal`**: Text (50). Originating portal (Default `AGMARKNET`).
* **`ingested_at`**: Timestamp. Data ingestion timestamp.

---

## 5. Table: `regulated_market_prices`

* **`price_id`**: Primary Key, Auto-incrementing Integer. Unique market price ID.
* **`price_date`**: Date, Not Null. Date of price recording (`YYYY-MM-DD`).
* **`market_location`**: Text (150), Not Null. Market site location.
* **`commodity_name`**: Text (100), Not Null. Name of agricultural commodity.
* **`retail_price_per_kg`**: Decimal (8,2). Retail price per kilogram in INR.
* **`wholesale_price_per_qtl`**: Decimal (10,2). Wholesale price per quintal in INR.
* **`source_url`**: Text. Direct source URL endpoint.
* **`ingested_at`**: Timestamp. Data ingestion timestamp.

---

## 6. Table: `crop_production_stats`

* **`stat_id`**: Primary Key, Auto-incrementing Integer. Unique production record ID.
* **`crop_year`**: Text (20), Not Null. Agricultural year (e.g., `2023-2024`).
* **`district_name`**: Text (100), Not Null. District jurisdiction.
* **`crop_name`**: Text (100), Not Null. Cultivated crop.
* **`area_hectares`**: Decimal (10,2). Cultivated area in hectares.
* **`production_metric_tonnes`**: Decimal (12,2). Total harvest volume in metric tonnes.
* **`yield_kg_per_hectare`**: Decimal (10,2). Calculated yield in kg per hectare.
* **`source_pdf_url`**: Text. DES PDF report source link.
* **`ingested_at`**: Timestamp. Data ingestion timestamp.

---

## 7. Table: `storage_warehouse_logistics`

* **`facility_id`**: Primary Key, Auto-incrementing Integer. Unique facility ID.
* **`society_name`**: Text (255), Not Null. Name of PACCS or storage co-operative.
* **`facility_type`**: Text (100). Facility type (`PACCS`, `Cold Storage`, `Warehouse`).
* **`region_name`**: Text (100), Not Null. Region location.
* **`capacity_metric_tonnes`**: Decimal (10,2). Storage capacity in metric tonnes.
* **`contact_details`**: Text. Address and phone numbers.
* **`source_url`**: Text. Direct source URL endpoint.
* **`ingested_at`**: Timestamp. Data ingestion timestamp.

---

## 8. Table: `scraped_logs`

* **`log_id`**: Primary Key, Auto-incrementing Integer. Unique log ID.
* **`url`**: Text, Not Null. Target scrape URL.
* **`status`**: Text Check (`SUCCESS`, `FAILED`). Status of extraction run.
* **`characters_extracted`**: Integer. Total extracted character length.
* **`timestamp`**: Timestamp. Log execution time.