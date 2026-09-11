from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import matches
from app.config import settings

app = FastAPI(
    title="Porvabet",
    description="Motore quantitativo di analisi pre-match per scommesse sportive",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
