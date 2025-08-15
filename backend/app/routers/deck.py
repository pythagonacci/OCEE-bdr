import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.prospect import Prospect
from ..models.deck import Deck
from ..schemas.deck import DeckOut
from ..services.ai import generate_deck_content, AIUnavailableError, AIFormatError
from ..services.pdf import render_deck_to_pdf, TemplateError, RenderError, FileIOError
from ..config import settings

router = APIRouter()

@router.post("/{prospect_id}/generate", response_model=DeckOut, status_code=status.HTTP_201_CREATED)
def generate_deck(prospect_id: int, db: Session = Depends(get_db)):
    # 1) fetch prospect
    p = db.get(Prospect, prospect_id)
    if not p:
        raise HTTPException(status_code=404, detail="Prospect not found")

    # 2) build prospect dict for AI
    prospect_dict = {
        "company_name": p.company_name,
        "contact_name": p.contact_name,
        "industry": p.industry,
        "revenue_range": p.revenue_range,
        "location": p.location,
        "sale_motivation": p.sale_motivation,
        "signals": p.signals,
    }

    # 3) generate slides via OpenAI (normalized)
    try:
        payload = generate_deck_content(prospect_dict)
    except AIUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except AIFormatError as e:
        raise HTTPException(status_code=502, detail=str(e))

    slides = payload["slides"]
    deck_title = payload["deck_title"]

    # 4) persist deck
    d = Deck(
        prospect_id=p.id,
        title=deck_title,
        slides_json=json.dumps(slides, ensure_ascii=False),
        pdf_path=None,
    )
    db.add(d)
    db.commit()
    db.refresh(d)

    pdf_url = None
    if d.pdf_path:
        pdf_url = settings.APP_BASE_URL.rstrip("/") + d.pdf_path

    return {
        "id": d.id,
        "prospect_id": d.prospect_id,
        "title": d.title,
        "slides": slides,
        "pdf_url": pdf_url,
    }

@router.post("/{deck_id}/render", response_model=DeckOut, status_code=status.HTTP_200_OK)
def render_deck(deck_id: int, db: Session = Depends(get_db)):
    d = db.get(Deck, deck_id)
    if not d:
        raise HTTPException(status_code=404, detail="Deck not found")

    slides = json.loads(d.slides_json)

    # Render to PDF & save path
    try:
        rel_path = render_deck_to_pdf(slides, d.title)  # e.g., "/generated/acme_x_offdeal.pdf"
    except (TemplateError, RenderError, FileIOError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    d.pdf_path = rel_path
    db.add(d)
    db.commit()
    db.refresh(d)

    pdf_url = settings.APP_BASE_URL.rstrip("/") + rel_path
    return {
        "id": d.id,
        "prospect_id": d.prospect_id,
        "title": d.title,
        "slides": slides,
        "pdf_url": pdf_url,
    }
