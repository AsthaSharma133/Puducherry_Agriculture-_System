import fitz  # PyMuPDF
import requests

def pdf_extractor(target: str) -> str:
    """Extracts text content from a local or remote PDF file using PyMuPDF."""
    try:
        if target.startswith("http://") or target.startswith("https://"):
            response = requests.get(target, timeout=15)
            response.raise_for_status()
            doc = fitz.open(stream=response.content, filetype="pdf")
        else:
            doc = fitz.open(target)

        text_content = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_content.append(f"--- Page {page_num + 1} ---\n" + page.get_text())

        full_text = "\n".join(text_content).strip()
        return full_text if full_text else "No text extracted from PDF."
    except Exception as e:
        return f"Error extracting PDF '{target}': {str(e)}"