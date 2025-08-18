from __future__ import annotations

import json
import logging
from typing import Any, Dict, List
from ..config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIUnavailableError(Exception):
    ...

class AIFormatError(Exception):
    ...

# Canonical slide order (always 5)
SCHEMA = [
    {"key": "cover", "title": "Cover"},
    {"key": "market_opportunity", "title": "Market Opportunity"},
    {"key": "why_offdeal", "title": "Why OffDeal"},
    {"key": "positioning", "title": "Positioning for Maximum Value"},
    {"key": "process_next_steps", "title": "Process & Next Steps"},
]

def _strip_markup(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", str(text or ""))
    text = re.sub(r"^[\-\•\*\s]+", "", text).strip()
    return re.sub(r"\s+", " ", text).strip()

def _truncate(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= max_chars else (text[: max_chars - 1].rstrip() + "…")

def _normalize_deck_obj(obj: Dict[str, Any]) -> tuple[list[dict], str]:
    """
    Coerce model output into an ordered slides array + title, padding any missing slides.
    """
    slides_out: List[Dict[str, Any]] = []
    for spec in SCHEMA:
        key = spec["key"]
        canonical = spec["title"]
        node = (obj or {}).get(key) or {}

        # Title
        title = _truncate(_strip_markup(node.get("title") or canonical), settings.TITLE_MAX_CHARS)

        # Bullets
        bullets_in = node.get("bullets") or []
        if not isinstance(bullets_in, list):
            bullets_in = []
        clean: List[str] = []
        for b in bullets_in:
            if not isinstance(b, str):
                continue
            s = _truncate(_strip_markup(b), settings.BULLET_MAX_CHARS)
            if s:
                clean.append(s)
        bullets = clean[: settings.MAX_BULLETS]

        slides_out.append({"title": title, "bullets": bullets})

    deck_title = (obj or {}).get("deck_title") or "OffDeal Pitch"
    deck_title = _truncate(_strip_markup(deck_title), settings.TITLE_MAX_CHARS) or "OffDeal Pitch"
    return slides_out, deck_title

def _openai_json_response(prompt: str) -> Dict[str, Any] | List[Any]:
    # Support local stub mode (no external calls)
    if getattr(settings, "STUB_MODE", False):
        logger.info("STUB_MODE=True: returning stubbed slides")
        return {
            "deck_title": "Your Business — Achieve a better sale with OffDeal",
            "cover": {"title": "Cover", "bullets": []},
            "market_opportunity": {"title": "Market Opportunity", "bullets": ["Industry tailwinds", "Consolidation", "Favorable rates"]},
            "why_offdeal": {"title": "Why OffDeal", "bullets": ["15× more buyers", "Offers <45 days", "~30% higher"]},
            "positioning": {"title": "Positioning for Maximum Value", "bullets": ["Recurring revenue", "Strong regional footprint"]},
            "process_next_steps": {"title": "Process & Next Steps", "bullets": ["NDA → CIM → Meetings → LOIs → Close"]},
        }

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
        logger.info("=== RAW AI OUTPUT ===")
        logger.info(raw_response)
        logger.info("=== END RAW AI OUTPUT ===")
        parsed_response = json.loads(raw_response)
        return parsed_response
    except Exception as e:
        raise AIUnavailableError(f"OpenAI call failed: {e!s}")

def generate_deck_content(prospect: Dict[str, Any]) -> dict:
    """
    Always produce 5 slides in SCHEMA order.
    - cover: title only (no bullets) -> "[Business] — Achieve a better sale with OffDeal"
    - market_opportunity: 3–7 concise, concrete bullets
    - why_offdeal: 3–7 bullets (15× buyers, <45-day offers, ~30% higher, no upfront fees, white-glove)
    - positioning: 3–7 bullets (no named buyers)
    - process_next_steps: 3–7 bullets (NDA → CIM → Meetings → LOIs → Close + CTA)
    """
    company = (prospect.get("company_name") or "").strip() or "Your Business"
    deck_title = f"{company} — Achieve a better sale with OffDeal"

    prospect_json = json.dumps(prospect, ensure_ascii=False)

    # Triple-quoted f-string: no escaping headaches
    prompt = f"""
You are an expert pitch deck copywriter for OffDeal (AI-native investment bank for SMBs).
Generate persuasive, personalized content for a 5-slide deck. Use Prospect Data where relevant,
but DO NOT include any prospect data on the cover slide. The cover is title only.

Return a single JSON object with exactly these keys: cover, market_opportunity, why_offdeal,
positioning, process_next_steps, and deck_title. Each key (except cover) must have a "title" and
3–7 bullets. Bullets should be concrete (metrics, timelines, buyer processes) and concise
(ideally 10–20 words). Avoid naming specific buyer companies anywhere.

Slide guidance:
- cover: title only (no bullets). Title must be exactly: "{deck_title}"
- market_opportunity: industry trends, timing; reflect prospect industry/region if present.
- why_offdeal: buyer network (15× more buyers), <45-day offers, ~30% higher offers, no upfront fees, white-glove.
- positioning: strengths (recurring revenue, share, IP); generalized language, no named buyers.
- process_next_steps: NDA → CIM → Buyer Meetings → LOIs → Close; clear CTA.

Prospect data:
{prospect_json}
"""

    raw = _openai_json_response(prompt)
    slides, _ = _normalize_deck_obj(raw)

    # Enforce cover and 5-slide guarantee
    slides[0]["title"] = deck_title
    slides[0]["bullets"] = []

    for i, spec in enumerate(SCHEMA):
        if not slides[i]["title"]:
            slides[i]["title"] = spec["title"]
        if spec["key"] != "cover" and not slides[i]["bullets"]:
            slides[i]["bullets"] = ["Content unavailable."]

    return {"slides": slides, "deck_title": deck_title}
