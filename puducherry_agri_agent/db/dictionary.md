# Database Dictionary

## Table: `sources`
- **source_id**: Primary key, auto-incrementing integer.
- **team_id**: Unique identifier for the contributing team (e.g., 35).
- **state**: Regional jurisdiction, default `'Puducherry'`.
- **source_name**: Descriptive title of the agricultural data source.
- **url**: Source URL endpoint.
- **period_of_info**: Temporal span of available source data (e.g., `2024–2026`).
- **modality**: Data delivery format (`Static Web HTML`, `Digital PDF`, `Dynamic Web HTML`).
- **description**: Summary of domain intelligence provided by the source.
- **limitations**: Inherent structural, formatting, or parsing restrictions.

## Table: `scraped_logs`
- **log_id**: Primary key, auto-incrementing integer.
- **url**: Targeted URL endpoint during execution.
- **status**: Scrape status indicator (`SUCCESS` or `FAILED`).
- **characters_extracted**: Total count of character output returned.
- **timestamp**: ISO timestamp recording execution time.