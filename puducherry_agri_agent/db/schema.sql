-- Database Schema for Puducherry Agriculture Information System

CREATE TABLE IF NOT EXISTS sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'Puducherry',
    source_name TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    period_of_info TEXT,
    modality TEXT CHECK(modality IN ('Static Web HTML', 'Digital PDF', 'Dynamic Web HTML')),
    description TEXT,
    limitations TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scraped_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    status TEXT CHECK(status IN ('SUCCESS', 'FAILED')),
    characters_extracted INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);