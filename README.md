# Troopod — AI Landing Page Personalizer

> Match your landing page to your ad creative automatically, using Claude AI + CRO principles.

## What it does

Users input:
1. A landing page URL
2. An ad creative (text description + optional image)

The system outputs a personalized version of that **same** landing page — with surgical text edits that create message match between the ad and the page, improving conversion.

## Live Demo
🔗 [troopod.vercel.app](https://troopod.vercel.app) ← update after deployment

## How it works

```
Ad creative + Landing page URL
         ↓
   Scraper fetches HTML
         ↓
   Claude AI analyzes ad vs page
         ↓
   Generates targeted edit plan (JSON)
         ↓
   Validation layer filters bad edits
         ↓
   Edit engine applies changes to HTML
         ↓
   Side-by-side personalized preview
```

## Tech Stack

| Layer | Tool |
|-------|------|
| AI | Claude (Anthropic) |
| Backend | FastAPI (Python) |
| Frontend | HTML/CSS/JS (no framework) |
| Deployment | Vercel (frontend) + Render (backend) |
| Scraping | BeautifulSoup4 + Requests |

## Local Setup

```bash
# 1. Clone
git clone https://github.com/suhanij41n/troopod.git
cd troopod

# 2. Install deps
cd backend && pip install -r requirements.txt

# 3. Add API key
echo "ANTHROPIC_API_KEY=your_key_here" > .env

# 4. Run backend
python main.py

# 5. Open frontend (new terminal)
cd ../frontend && python -m http.server 3000
# Visit http://localhost:3000
```

## Safety Systems

See [GUARDRAILS.md](./GUARDRAILS.md) for full documentation of:
- Hallucination prevention
- Broken UI prevention
- Inconsistent output handling
- Page fetch error handling

## Project Structure

```
troopod/
├── backend/
│   ├── main.py          # FastAPI server & routes
│   ├── analyzer.py      # Claude AI integration
│   ├── scraper.py       # HTML fetch & text extraction
│   └── requirements.txt
├── frontend/
│   └── index.html       # Full UI (single file)
├── GUARDRAILS.md        # Safety system docs
├── vercel.json          # Vercel deployment config
├── render.yaml          # Render.com backend config
└── README.md
```

## Built by
Suhani Jain — AI PM Internship Assignment, Troopod
