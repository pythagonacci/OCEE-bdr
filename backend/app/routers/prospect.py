from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models
from ..schemas.prospect import ProspectCreate, ProspectOut

router = APIRouter()

@router.post("", response_model=ProspectOut, status_code=status.HTTP_201_CREATED)
def create_prospect(payload: ProspectCreate, db: Session = Depends(get_db)):
    p = models.Prospect(
        company_name=payload.company_name.strip(),
        contact_name=(payload.contact_name or None),
        email=(str(payload.email) if payload.email else None),
        industry=(payload.industry or None),
        revenue_range=(payload.revenue_range or None),
        location=(payload.location or None),
        sale_motivation=(payload.sale_motivation or None),
        signals=(payload.signals or None),
        notes=(payload.notes or None),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.get("", response_model=List[ProspectOut])
def list_prospects(db: Session = Depends(get_db)):
    return db.query(models.Prospect).order_by(models.Prospect.created_at.desc()).all()

@router.get("/{prospect_id}", response_model=ProspectOut)
def get_prospect(prospect_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Prospect).get(prospect_id)
    if not p:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return p
