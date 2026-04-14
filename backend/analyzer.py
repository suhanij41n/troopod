import anthropic
import json
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ─── SYSTEM PROMPT ──────────────────────────────────────────────────────────────
# This is the most important part of the whole system.
# It tells Claude exactly what role it plays, what it must and must not do,
# and how to format its output for our edit engine.

SYSTEM_PROMPT = """You are an expert Conversion Rate Optimization (CRO) specialist and landing page personalization engine.

Your job is to analyze an ad creative and a landing page, then suggest MINIMAL, HIGH-IMPACT text edits that:
1. Create message match between the ad and the page (visitor feels the page matches what the ad promised)
2. Reinforce the specific offer, benefit, or audience from the ad
3. Strengthen CTAs to match the ad's urgency/tone
4. Improve conversion without changing layout, design, or structure

STRICT RULES — you must follow all of these:
- Only suggest edits to TEXT content (headlines, CTAs, paragraphs, sub-headlines)
- NEVER change layout, CSS classes, image alt text, or HTML structure
- NEVER invent facts, statistics, or claims not supported by the original page
- Keep edits believable and within the brand voice of the original page
- Maximum 8 edits per run — focus on the highest-impact changes only
- Each new_text must be close in length to the original (±40% word count)
- If an element is already well-matched to the ad, do NOT suggest an edit for it

OUTPUT FORMAT — return ONLY valid JSON, no explanation, no markdown, no code blocks:
{
  "ad_analysis": {
    "main_message": "what the ad is saying",
    "target_audience": "who the ad targets",
    "key_offer": "the specific offer or value prop",
    "tone": "emotional tone of the ad",
    "urgency": "low/medium/high"
  },
  "page_analysis": {
    "current_headline": "what the page currently says",
    "message_match_score": 1-10,
    "biggest_gap": "the most important mismatch between ad and page"
  },
  "edits": [
    {
      "element_type": "h1/h2/h3/cta_button/hero_text/subheadline/paragraph",
      "original_text": "EXACT text from the page, copy-paste accurate",
      "new_text": "your improved version",
      "reason": "one sentence explaining why this edit improves conversion",
      "confidence": "high/medium/low"
    }
  ],
  "summary": "2-3 sentence summary of the personalization strategy"
}"""


def analyze_ad_and_page(
    ad_description: str,
    page_text_elements: dict,
    ad_image_url: str = None
) -> dict:
    """
    Main function: takes ad info + page elements, returns Claude's edit plan.
    
    Parameters:
    - ad_description: text description of the ad (required)
    - page_text_elements: dict from scraper.extract_text_elements()
    - ad_image_url: optional URL of ad image for vision analysis
    
    Returns dict with keys: success, data (parsed JSON), raw_response, error
    """

    # Build the user message content
    user_content = []

    # If an ad image URL is provided, include it for vision
    if ad_image_url:
        user_content.append({
            "type": "text",
            "text": "Here is the ad creative image to analyze:"
        })
        user_content.append({
            "type": "image",
            "source": {
                "type": "url",
                "url": ad_image_url
            }
        })

    # Build the text prompt with ad + page data
    page_summary = format_page_elements(page_text_elements)

    user_content.append({
        "type": "text",
        "text": f"""AD CREATIVE DESCRIPTION:
{ad_description}

LANDING PAGE TEXT ELEMENTS:
{page_summary}

Based on the ad creative above, suggest targeted text edits to personalize this landing page.
Remember: return ONLY the JSON object, nothing else."""
    })

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )

        raw_text = response.content[0].text.strip()

        # Parse and validate the JSON response
        parsed = safe_parse_json(raw_text)

        if parsed is None:
            return {
                "success": False,
                "data": None,
                "raw_response": raw_text,
                "error": "Claude returned invalid JSON. Raw response saved for debugging."
            }

        # Validate the structure has what we need
        if "edits" not in parsed:
            return {
                "success": False,
                "data": parsed,
                "raw_response": raw_text,
                "error": "Response missing 'edits' key."
            }

        # Filter out low-confidence edits if there are enough high-confidence ones
        edits = parsed.get("edits", [])
        high_confidence = [e for e in edits if e.get("confidence") == "high"]
        if len(high_confidence) >= 3:
            parsed["edits"] = high_confidence + [e for e in edits if e.get("confidence") == "medium"]

        return {
            "success": True,
            "data": parsed,
            "raw_response": raw_text,
            "error": None
        }

    except anthropic.APIConnectionError:
        return {"success": False, "data": None, "raw_response": None,
                "error": "Could not connect to Claude API. Check your internet connection."}
    except anthropic.AuthenticationError:
        return {"success": False, "data": None, "raw_response": None,
                "error": "Invalid API key. Check your ANTHROPIC_API_KEY in .env"}
    except anthropic.RateLimitError:
        return {"success": False, "data": None, "raw_response": None,
                "error": "Rate limit hit. Wait a moment and try again."}
    except Exception as e:
        return {"success": False, "data": None, "raw_response": None, "error": str(e)}


def format_page_elements(elements: dict) -> str:
    """
    Formats the extracted page elements into a clean string for Claude to read.
    """
    lines = []

    mapping = {
        "h1": "H1 (Main Headline)",
        "h2": "H2 (Sub-headlines)",
        "h3": "H3 (Section Headers)",
        "cta_buttons": "CTA Buttons",
        "hero_text": "Hero Paragraphs",
        "subheadlines": "Sub-headlines",
        "body_paragraphs": "Body Paragraphs",
    }

    for key, label in mapping.items():
        items = elements.get(key, [])
        if items:
            lines.append(f"\n[{label}]")
            for i, item in enumerate(items[:5], 1):  # Cap at 5 per type
                text = item.get("original", "")
                if text:
                    lines.append(f"  {i}. \"{text}\"")

    return "\n".join(lines) if lines else "No text elements extracted."


def safe_parse_json(text: str) -> dict | None:
    """
    Attempts to parse JSON from Claude's response.
    Handles common cases where Claude adds markdown code fences.
    """
    if not text:
        return None

    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last line (the ``` markers)
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
    return None


def validate_edit(edit: dict, original_html: str) -> dict:
    """
    Validates a single edit before applying it.
    Returns the edit with an added 'valid' boolean and 'reason' if invalid.
    """
    original = edit.get("original_text", "").strip()
    new_text = edit.get("new_text", "").strip()

    # Check 1: Both fields present
    if not original or not new_text:
        edit["valid"] = False
        edit["validation_note"] = "Missing original_text or new_text"
        return edit

    # Check 2: Not the same text
    if original == new_text:
        edit["valid"] = False
        edit["validation_note"] = "Edit is identical to original"
        return edit

    # Check 3: Original text exists in the HTML
    if original not in original_html:
        edit["valid"] = False
        edit["validation_note"] = "Original text not found in page HTML (hallucination risk)"
        return edit

    # Check 4: New text is not drastically longer (UI safety)
    orig_words = len(original.split())
    new_words = len(new_text.split())
    if new_words > orig_words * 2.5:
        edit["valid"] = False
        edit["validation_note"] = f"New text is too long ({new_words} words vs {orig_words} original)"
        return edit

    # Check 5: No suspicious content
    suspicious = ["<script", "<img", "javascript:", "onclick=", "href="]
    for s in suspicious:
        if s in new_text.lower():
            edit["valid"] = False
            edit["validation_note"] = f"New text contains disallowed content: {s}"
            return edit

    edit["valid"] = True
    edit["validation_note"] = "Passed all checks"
    return edit