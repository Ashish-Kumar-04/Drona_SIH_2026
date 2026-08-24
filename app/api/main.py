"""
FastAPI Server Entrypoint for SIH Problem Statement 25073.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.session import init_db
from app.api.routes import router

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-Powered Mobile Platform for Democratizing Sports Talent Assessment (SIH Problem Statement 25073)",
    version=settings.VERSION
)

# CORS: explicit allow-list of browser origins (never "*" together with credentials).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    if settings.jwt_key_is_default:
        logger.warning(
            "JWT_SECRET_KEY is the insecure development default. "
            "Set a strong JWT_SECRET_KEY in your .env before deploying."
        )


app.include_router(router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "status": "ONLINE",
        "project": settings.PROJECT_NAME,
        "problem_statement_id": settings.PROBLEM_STATEMENT_ID,
        "version": settings.VERSION,
        "benchmark_source": settings.BENCHMARK_SOURCE_LABEL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
