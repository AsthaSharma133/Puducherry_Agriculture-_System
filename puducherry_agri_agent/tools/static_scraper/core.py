import requests
from bs4 import BeautifulSoup

def static_scraper(url: str) -> str:
    """Scrapes static HTML content from a given URL using BeautifulSoup."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text(separator=' ', strip=True)
        return text if text else "No printable content extracted."
    except Exception as e:
        return f"Error scraping URL '{url}': {str(e)}"