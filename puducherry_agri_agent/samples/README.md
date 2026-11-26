# Samples (Quick Start)

Single pages cut from the full Season & Crop Report PDFs (S3), so the pipeline can be
tried without downloading the 30 MB corpus. The full PDFs are git-ignored; fetch them with
`python scripts/fetch_corpus.py` or use the team's Google Drive copy.

| File | Source | What it shows |
|---|---|---|
| `S3_SCR_2020-21_p50_tableVB_text_layer.pdf` | S3 2020-21, PDF page 50 | Table V-B (total out-turn by region). Has a text layer: PyMuPDF reads it directly. |
| `S3_SCR_2021-22_p49_tableVB_vector_needs_OCR.pdf` | S3 2021-22, PDF page 49 | Same table, but the glyphs are drawn as vector outlines (no text layer, no image): needs OCR. |
