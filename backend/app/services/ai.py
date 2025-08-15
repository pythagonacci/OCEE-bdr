from __future__ import annotations

import json
import logging
from typing import Any, Dict, List
from ..config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fixed slide schema (order + canonical titles)
SLIDE_SCHEMA = [
    {"key": "cover",               "title": "Personalized Cover"},
    {"key": "market_opportunity",  "title": "Market Opportunity"},
    {"key": "why_offdeal",         "title": "Why OffDeal"},
    {"key": "positioning",         "title": "Positioning for Maximum Value"},
    {"key": "process_next_steps",  "title": "Process & Next Steps"},
]

class AIUnavailableError(Exception):
    pass

class AIFormatError(Exception):
    pass

def _strip_markup(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", str(text or ""))
    text = re.sub(r"^[\-\•\*\s]+", "", text).strip()
    return re.sub(r"\s+", " ", text).strip()

def _truncate(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= max_chars else (text[: max_chars - 1].rstrip() + "…")

def _normalize_deck_obj(obj: Dict[str, Any]) -> tuple[list[dict], str]:
    """Coerce model output into an ordered slides array + title."""
    slides_out: List[Dict[str, Any]] = []
    for spec in SLIDE_SCHEMA:
        key = spec["key"]
        canonical = spec["title"]
        node = obj.get(key) or {}

        # Title
        title = _truncate(_strip_markup(node.get("title") or canonical), settings.TITLE_MAX_CHARS)

        # Bullets
        bullets = node.get("bullets") or []
        if not isinstance(bullets, list):
            bullets = []
        clean: List[str] = []
        for b in bullets:
            if not isinstance(b, str):
                continue
            s = _truncate(_strip_markup(b), settings.BULLET_MAX_CHARS)
            if s:
                clean.append(s)
        bullets = clean[: settings.MAX_BULLETS] or ["Content unavailable."]

        # Optional guardrail example: avoid named buyers on positioning
        if key == "positioning":
            import re
            bullets = [re.sub(r"(?i)\b(buyer|acquirer|company)\s*:\s*[\w\-\.\& ]+", "buyer: (generalized)", x) for x in bullets]

        slides_out.append({"title": title, "bullets": bullets})

    deck_title = obj.get("deck_title") or SLIDE_SCHEMA[0]["title"]
    deck_title = _truncate(_strip_markup(deck_title), settings.TITLE_MAX_CHARS) or "OffDeal Pitch"
    return slides_out, deck_title

def _openai_json_response(prompt: str) -> Dict[str, Any] | List[Any]:
    try:
        from openai import OpenAI
    except Exception as e:
        raise AIUnavailableError(f"OpenAI SDK not available: {e!s}")

    if not settings.OPENAI_API_KEY:
        raise AIUnavailableError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw_response = resp.choices[0].message.content
        parsed_response = json.loads(raw_response)

        # Log the raw AI output
        logger.info("=== RAW AI OUTPUT ===")
        logger.info(f"Raw JSON response: {raw_response}")
        logger.info("=== END RAW AI OUTPUT ===")

        return parsed_response
    except Exception as e:
        raise AIUnavailableError(f"OpenAI call failed: {e!s}")

def generate_deck_content(prospect: Dict[str, Any]) -> dict:
    """
    Build one prompt for all slides, call OpenAI, normalize, and return:
      {
        "slides": [ {title, bullets[]}, ...schema order... ],
        "deck_title": "<Company> x OffDeal"
      }
    """
    # Build the new, OffDeal-specific, personalization-required prompt
    prospect_json = json.dumps(prospect, ensure_ascii=False)
    prompt = (
        "You are an expert pitch deck copywriter for OffDeal, the world’s first AI-native investment bank for small businesses ($5M–$100M revenue). "
        "Your job is to generate professional, persuasive, and personalized content for a 5-slide pitch deck for a business owner considering a sale.\n"
        "Personalization is required: You must use the provided Prospect Data in every slide where relevant. Prospect Data should influence tone, examples, and specific points—do not produce generic content. "
        "If any Prospect Data fields are missing, make reasonable assumptions but keep the language consistent with the rest of the deck.\n\n"
        "About OffDeal\n"
        "Mission: Revolutionize M&A for SMBs by combining AI-driven technology with white-glove advisory services.\n\n"
        "Proven Results: Examples include selling an HVAC company in 16 days at a premium valuation.\n\n"
        "Buyer Network: Proprietary, AI-powered buyer platform that finds 15× more buyers than traditional advisors.\n\n"
        "Speed: Generates competitive offers in under 45 days.\n\n"
        "Higher Valuations: Achieves ~30% higher offers by matching sellers with strategic buyers.\n\n"
        "No Upfront Fees: Eliminates seller risk.\n\n"
        "White-Glove Support: Personal, hands-on guidance throughout the entire process.\n\n"
        "Slide Structure & Content Requirements\n"
        "Personalized Cover — Company name, owner name, hook line, revenue range, key signals. Show this deck is made specifically for them.\n\n"
        "Market Opportunity — Relevant industry trends, timing factors, market triggers that make now a great time to sell.\n\n"
        "Why OffDeal — Explain why OffDeal is the best partner, using the details above. Include buyer network, auction-style process, 120-day close timeline, NDA screening, hands-on preparation. Emphasize advantage over DIY sales.\n\n"
        "Positioning for Maximum Value — Highlight the business’s strengths (recurring revenue, market share, unique IP, strategic advantages) and how OffDeal will present them to maximize appeal—no specific buyer names.\n\n"
        "Process & Next Steps — Visual or bullet overview: NDA → CIM → Buyer Meetings → LOIs → Close; include clear CTA for confidential conversation.\n\n"
        "Return a single JSON object with exactly these keys: cover, market_opportunity, why_offdeal, positioning, process_next_steps, and deck_title.\n"
        "Each key must map to an object with title and bullets (a list of 3–5 concise bullet points).\n"
        "Avoid naming any specific buyers on the positioning slide; keep language generalized and professional.\n\n"
        "Prospect data:\n"
        f"{prospect_json}"
    )

    raw = _openai_json_response(prompt)
    slides, deck_title = _normalize_deck_obj(raw)
    return {"slides": slides, "deck_title": deck_title}

