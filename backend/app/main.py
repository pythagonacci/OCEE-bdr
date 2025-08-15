from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .config import settings
from .database import Base, engine

app = FastAPI(title="OffDeal BDR Engine API")

# --- CORS ---
origins = settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DB ---
Base.metadata.create_all(bind=engine)

# --- Paths ---
BASE_DIR = os.path.dirname(__file__)                    # .../backend/app
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))  # .../backend

# Static (logo, etc.) lives at: backend/static
STATIC_DIR = os.path.abspath(os.path.join(PROJECT_DIR, "static"))
os.makedirs(STATIC_DIR, exist_ok=True)

# Generated PDFs dir can be relative (e.g. "./app/generated") or absolute
if os.path.isabs(settings.FILE_STORAGE_DIR):
    GENERATED_DIR = settings.FILE_STORAGE_DIR
else:
    GENERATED_DIR = os.path.abspath(os.path.join(PROJECT_DIR, settings.FILE_STORAGE_DIR))
os.makedirs(GENERATED_DIR, exist_ok=True)

# --- Static mounts ---
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/generated", StaticFiles(directory=GENERATED_DIR), name="generated")

# --- Routers ---
from .routers import prospect as prospect_router
from .routers import deck as deck_router

app.include_router(prospect_router.router, prefix="/prospects", tags=["prospects"])
app.include_router(deck_router.router, prefix="/decks", tags=["decks"])

# --- Optional: simple health check ---
@app.get("/healthz", tags=["meta"])
def healthz():
    return {"status": "ok"}
