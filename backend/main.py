from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional
import uvicorn

from scraper import fetch_page, apply_edits_to_html
from analyzer import analyze_ad_and_page, validate_edit

app = FastAPI(
    title="Troopod Landing Page Personalizer",
    description="AI-powered landing page personalization based on ad creative",
    version="1.0.0"
)

# Allow requests from the frontend (Vercel, localhost, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REQUEST / RESPONSE MODELS ──────────────────────────────────────────────────

class PersonalizeRequest(BaseModel):
    landing_page_url: str
    ad_description: str
    ad_image_url: Optional[str] = None


class PersonalizeResponse(BaseModel):
    success: bool
    original_url: str
    ad_analysis: dict
    page_analysis: dict
    edits_applied: list
    edits_skipped: list
    personalized_html: str
    summary: str
    message_match_score: int
    error: Optional[str] = None


# ─── ROUTES ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Troopod Personalizer API is running", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/personalize")
async def personalize(req: PersonalizeRequest):
    """
    Main endpoint: takes ad + URL, returns personalized HTML + edit plan.
    
    Flow:
    1. Fetch and parse the landing page
    2. Send ad + page elements to Claude
    3. Validate each edit Claude suggests
    4. Apply valid edits to raw HTML
    5. Return everything (original, modified, edit plan, analysis)
    """

    # ── Step 1: Fetch the landing page ──────────────────────────────────────
    print(f"[1/4] Fetching page: {req.landing_page_url}")
    page_result = fetch_page(req.landing_page_url)

    if page_result["error"]:
        raise HTTPException(
            status_code=422,
            detail=f"Could not fetch landing page: {page_result['error']}"
        )

    raw_html = page_result["raw_html"]
    text_elements = page_result["text_elements"]

    # ── Step 2: Run Claude analysis ──────────────────────────────────────────
    print(f"[2/4] Sending to Claude AI for analysis...")
    analysis = analyze_ad_and_page(
        ad_description=req.ad_description,
        page_text_elements=text_elements,
        ad_image_url=req.ad_image_url
    )

    if not analysis["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"AI analysis failed: {analysis['error']}"
        )

    data = analysis["data"]
    proposed_edits = data.get("edits", [])

    # ── Step 3: Validate each edit ───────────────────────────────────────────
    print(f"[3/4] Validating {len(proposed_edits)} proposed edits...")
    validated_edits = [validate_edit(e, raw_html) for e in proposed_edits]
    valid_edits = [e for e in validated_edits if e.get("valid")]
    invalid_edits = [e for e in validated_edits if not e.get("valid")]

    print(f"      ✓ {len(valid_edits)} valid | ✗ {len(invalid_edits)} rejected")

    # ── Step 4: Apply edits to HTML ──────────────────────────────────────────
    print(f"[4/4] Applying edits to HTML...")
    personalized_html, applied, skipped = apply_edits_to_html(raw_html, valid_edits)

    # ── Step 5: Return full result ───────────────────────────────────────────
    return {
        "success": True,
        "original_url": req.landing_page_url,
        "ad_analysis": data.get("ad_analysis", {}),
        "page_analysis": data.get("page_analysis", {}),
        "edits_applied": applied,
        "edits_skipped": skipped + invalid_edits,
        "personalized_html": personalized_html,
        "summary": data.get("summary", ""),
        "message_match_score": data.get("page_analysis", {}).get("message_match_score", 0),
        "error": None
    }


@app.get("/preview", response_class=HTMLResponse)
async def preview_page(url: str):
    """
    Simple utility: fetch and return raw HTML of any URL (for debugging).
    """
    result = fetch_page(url)
    if result["error"]:
        return HTMLResponse(f"<h1>Error: {result['error']}</h1>", status_code=422)
    return HTMLResponse(result["raw_html"])


# ─── LOCAL DEV RUNNER ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)