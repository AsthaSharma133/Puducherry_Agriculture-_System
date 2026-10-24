# Static Agent Documentation

## Purpose
The Static Agent ingests, parses, and formats data from static HTML web pages across the official Puducherry Department of Agriculture portals.

## Implementation Details
- **Parser**: BeautifulSoup4 (`html.parser`).
- **HTTP Client**: Requests library with standard user-agent spoofing and automated retry/timeout management.
- **Output**: Cleaned, unformatted raw string text stripped of JavaScript script blocks and inline CSS layout tags.