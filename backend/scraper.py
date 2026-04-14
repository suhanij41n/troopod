import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def fetch_page(url: str) -> dict:
    """
    Fetches a landing page and returns:
    - raw_html: the full HTML string
    - text_elements: a structured dict of editable text elements
    - error: None or an error message string
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        html = response.text
        elements = extract_text_elements(html)
        return {"raw_html": html, "text_elements": elements, "error": None}
    except requests.exceptions.Timeout:
        return {"raw_html": None, "text_elements": None, "error": "Request timed out. The page took too long to respond."}
    except requests.exceptions.ConnectionError:
        return {"raw_html": None, "text_elements": None, "error": "Could not connect. Check that the URL is correct and publicly accessible."}
    except requests.exceptions.HTTPError as e:
        return {"raw_html": None, "text_elements": None, "error": f"HTTP error {e.response.status_code}: {e.response.reason}"}
    except Exception as e:
        return {"raw_html": None, "text_elements": None, "error": str(e)}


def extract_text_elements(html: str) -> dict:
    """
    Extracts the editable text elements from a page.
    We ONLY extract text — never layout, images, or CSS.
    This is what keeps the UI from breaking.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content tags entirely
    for tag in soup(["script", "style", "noscript", "svg", "head", "footer", "nav"]):
        tag.decompose()

    elements = {
        "h1": [],
        "h2": [],
        "h3": [],
        "cta_buttons": [],
        "hero_text": [],
        "subheadlines": [],
        "body_paragraphs": [],
    }

    # H1 — usually the main headline
    for tag in soup.find_all("h1"):
        text = clean_text(tag.get_text())
        if text:
            elements["h1"].append({"original": text, "selector": str(tag)[:80]})

    # H2 — sub-headlines / section headers
    for tag in soup.find_all("h2"):
        text = clean_text(tag.get_text())
        if text and len(text) > 5:
            elements["h2"].append({"original": text, "selector": str(tag)[:80]})

    # H3 — tertiary headlines
    for tag in soup.find_all("h3"):
        text = clean_text(tag.get_text())
        if text and len(text) > 5:
            elements["h3"].append({"original": text, "selector": str(tag)[:80]})

    # CTA Buttons — buttons and links that look like CTAs
    cta_patterns = re.compile(
        r"(get|start|try|sign.?up|join|buy|order|download|claim|book|schedule|request|demo|free|now)",
        re.IGNORECASE
    )
    for tag in soup.find_all(["button", "a"]):
        text = clean_text(tag.get_text())
        if text and len(text) > 2 and cta_patterns.search(text):
            elements["cta_buttons"].append({"original": text, "selector": str(tag)[:80]})

    # Hero text — large paragraphs near the top (first 3 <p> tags)
    all_p = soup.find_all("p")
    for tag in all_p[:3]:
        text = clean_text(tag.get_text())
        if text and len(text) > 20:
            elements["hero_text"].append({"original": text, "selector": str(tag)[:80]})

    # Body paragraphs — remaining <p> tags
    for tag in all_p[3:12]:
        text = clean_text(tag.get_text())
        if text and len(text) > 20:
            elements["body_paragraphs"].append({"original": text, "selector": str(tag)[:80]})

    return elements


def clean_text(text: str) -> str:
    """Strips whitespace and collapses internal spaces."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def apply_edits_to_html(raw_html: str, edits: list) -> str:
    """
    Applies Claude's suggested text edits to the raw HTML.
    Each edit is: {"original_text": "...", "new_text": "...", "element_type": "..."}
    
    Strategy: simple string replacement on the visible text.
    We never touch CSS, classes, IDs, or structure — just the text content.
    """
    modified_html = raw_html

    applied = []
    skipped = []

    for edit in edits:
        original = edit.get("original_text", "").strip()
        new_text = edit.get("new_text", "").strip()

        if not original or not new_text:
            skipped.append(edit)
            continue

        if original == new_text:
            skipped.append(edit)
            continue

        # Safety: don't apply if original text not found in HTML
        if original not in modified_html:
            skipped.append({"reason": "not found in HTML", **edit})
            continue

        # Apply the replacement
        modified_html = modified_html.replace(original, new_text, 1)
        applied.append(edit)

    return modified_html, applied, skipped