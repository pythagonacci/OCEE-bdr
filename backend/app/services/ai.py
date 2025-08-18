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

def _coerce_bullets(value: Any) -> List[str]:
    """
    Accept bullets as list[str], str with delimiters, or anything else (-> []).
    Splits on newlines/semicolon/dot/bullet chars, trims, de-dups empties.
    """
    if isinstance(value, list):
        raw = [x for x in value if isinstance(x, str)]
    elif isinstance(value, str):
        import re
        # Split on line breaks or common bullet separators
        parts = re.split(r"[;\n•\-\u2022\u2023\u2043]+", value)
        raw = [p.strip() for p in parts]
    else:
        raw = []

    out: List[str] = []
    for b in raw:
        clean = _truncate(_strip_markup(b), settings.BULLET_MAX_CHARS)
        if clean:
            out.append(clean)
    return out[: settings.MAX_BULLETS]

def _normalize_deck_obj(obj: Dict[str, Any] | None) -> tuple[List[Dict[str, Any]], str]:
    """
    Coerce model output into an ordered slides array + title, padding any missing slides.
    Tolerates malformed shapes, e.g. strings where dicts are expected.
    """
    obj = obj or {}
    slides_out: List[Dict[str, Any]] = []

    for spec in SCHEMA:
        node = obj.get(spec["key"])
        # Coerce non-dict nodes into expected shape
        if isinstance(node, str):
            node = {"title": node, "bullets": []}
        elif not isinstance(node, dict) or node is None:
            node = {}

        title_in = node.get("title")
        bullets_in = node.get("bullets")

        title = _truncate(_strip_markup(title_in or spec["title"]), settings.TITLE_MAX_CHARS)
        bullets = _coerce_bullets(bullets_in)

        slides_out.append({"title": title, "bullets": bullets})

    deck_title_raw = obj.get("deck_title")
    if isinstance(deck_title_raw, (dict, list)):
        deck_title_raw = ""
    deck_title = _truncate(_strip_markup(deck_title_raw or "OffDeal Pitch"), settings.TITLE_MAX_CHARS) or "OffDeal Pitch"
    return slides_out, deck_title

def _openai_json_response(prompt: str) -> Dict[str, Any] | List[Any]:
    # Support local stub mode (no external calls)
    if getattr(settings, "STUB_MODE", False):
        logger.info("STUB_MODE=True: returning stubbed slides")
        return {
            "deck_title": "Your Business — Achieve a better sale with OffDeal",
            "cover": "Cover",
            "market_opportunity": {
                "title": "Market Opportunity",
                "bullets": ["Industry tailwinds drive deal activity", "Consolidation creates seller leverage", "Favorable financing boosts valuations"]
            },
            "why_offdeal": {
                "title": "Why OffDeal",
                "bullets": ["AI matches 15x more buyers", "Initial offers in <45 days", "Auctions drive ~30% higher offers"]
            },
            "positioning": {
                "title": "Positioning for Maximum Value",
                "bullets": ["Strong recurring revenue model", "Scalable operations attract buyers"]
            },
            "process_next_steps": {
                "title": "Process & Next Steps",
                "bullets": ["NDA → CIM → Buyer Meetings → LOIs → Close", "Contact us to maximize value"]
            },
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
    - market_opportunity: 3–7 concrete bullets
    - why_offdeal: 3–7 bullets (15× buyers, <45-day offers, ~30% higher, no upfront fees, white-glove)
    - positioning: 3–7 bullets (no named buyers)
    - process_next_steps: 3–7 bullets (NDA → CIM → Meetings → LOIs → Close + CTA)
    """
    company = (prospect.get("company_name") or "").strip() or "Your Business"
    deck_title = f"{company} — Achieve a better sale with OffDeal"

    prospect_json = json.dumps(prospect, ensure_ascii=False)
    prompt = f"""
You are an expert in SMB M&A (small/medium businesses with $5M-$100M revenue) and a pitch deck copywriter for OffDeal, an AI-native investment bank revolutionizing SMB exits.

Background on SMB M&A:
Traditional SMB M&A faces challenges: limited buyer pools (often <100), long timelines (6-12 months average), low offers due to lack of competition, high upfront fees (retainers up to $50K+), and complex due diligence. In 2025, global M&A volumes declined 9% in H1 compared to H1 2024, but deal values rose 15% (per PwC mid-year outlook), reflecting selective buyers focusing on high-quality, scalable assets. SMB acquisitions are surging due to aging business owners retiring en masse, easier access to financing amid lower interest rates, and AI-driven tools streamlining processes. Sector-specific trends include: healthcare deal volumes up 75% YoY in Q1, driven by consolidation and tech-enabled services; retail median sale prices up 13%; service-based transactions up 7%; business services with tech integration seeing strong PE interest; overall growth in deal supply across industries like manufacturing, consumer, and technology (per Axial Q2 report). Buyers prioritize fundamentals like recurring revenue, growth potential, and low-risk profiles, with private equity firms actively pursuing mid-sized businesses, corporate acquirers accounting for ~71% of deals despite regulatory hurdles (per Goldman Sachs), and emerging influences like tariffs reshaping structures and virtual dealmaking accelerating timelines.

OffDeal's Approach:
OffDeal addresses these pains with a modern, AI-driven process: AI algorithm matches 1,000+ strategic buyers (15x more than traditional), runs competitive auctions for ~30% higher offers, delivers initial offers in <45 days (vs. 4-6 months), charges $0 upfront fees (success-based only), and provides white-glove support from dedicated M&A advisors—including end-to-end guidance, CIM preparation, one-on-one buyer meetings, and negotiation expertise. This maximizes value, speeds exits, and engages high-intent buyers with sector expertise, as proven by testimonials (e.g., 16-day sales, 71 NDAs).

Instructions for Analyzing Industry-Specific M&A Trends:
If the prospect data includes an industry (or can be inferred), analyze current 2025 M&A trends for that specific industry to inform the deck, especially market_opportunity. Follow these steps:
1. Identify the core industry and any sub-sectors/regions from prospect data.
2. Draw from factual 2025 trends (use the background above and your knowledge): assess deal volume changes (e.g., increases in healthcare or services), valuation shifts (e.g., higher multiples in retail/tech), key drivers (e.g., consolidation due to aging owners, technology adoption like AI, regulatory changes, economic factors like lower rates enabling financing), buyer types and interest (e.g., PE firms targeting scalable firms, strategic acquirers in consolidating sectors), and timing factors (e.g., surges in Q2 deal supply, optimism from favorable regulations).
3. Ensure analysis is relevant and factual—provide detailed insights without conciseness constraints where needed, but tie directly to why it's an opportune time for exit (e.g., rising values amid selective buying creates seller advantages).
4. For example: In healthcare, highlight 75% YoY deal volume rise driven by tech integration and demographics; in retail, note 13% price increases from consumer shifts; if no specific industry, use general SMB trends like value growth despite volume dips.
5. Integrate these analyzed trends into bullets persuasively, showing how OffDeal leverages them (e.g., AI matching taps into PE interest for faster, higher-value sales).

Generate persuasive, personalized content for a 5-slide deck. Use Prospect Data to tailor content: apply M&A insights and trend analysis to the specific industry/region if provided (e.g., weave in drivers or valuations in market_opportunity; emphasize sellable strengths like growth metrics in positioning). Make bullets thorough yet focused (15-30 words ideal), concrete (use metrics, timelines, contrasts to traditional M&A), and persuasive (show how OffDeal improves outcomes). DO NOT include any prospect data on the cover slide. Avoid naming specific buyer companies anywhere.

Return a single JSON object with exactly these keys: cover, market_opportunity, why_offdeal, positioning, process_next_steps, and deck_title. Each key (except cover) must have a "title" and 3–7 bullets.

Slide guidance:
- cover: title only (no bullets). Title must be exactly: "{deck_title}"
- market_opportunity: Title like "Market Opportunity in [Industry]". Bullets on industry trends, M&A timing, buyer interest; incorporate analyzed 2025 trends and prospect specifics (e.g., consolidation, PE demand) to show why now is ideal for exit.
- why_offdeal: Title like "Why Choose OffDeal". Bullets contrasting traditional pains with OffDeal's benefits: 15x more buyers via AI, <45-day offers, ~30% higher via auctions, no fees, white-glove advisory.
- positioning: Title like "Your Business Positioning". Bullets on strengths in M&A context (e.g., recurring revenue, market share, IP, scalability); use generalized language, tie to buyer appeal without names.
- process_next_steps: Title like "Our Proven Process & Next Steps". Bullets outlining NDA → CIM → Buyer Meetings → LOIs → Close; emphasize speed/efficiency, end with clear CTA (e.g., "Schedule a call to start").

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