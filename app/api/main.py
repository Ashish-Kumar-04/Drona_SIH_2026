"""
FastAPI Server Entrypoint for SIH Problem Statement 25073.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.session import init_db
from app.api.routes import router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-Powered Mobile Platform for Democratizing Sports Talent Assessment (SIH Problem Statement 25073)",
    version=settings.VERSION
)

# CORS middleware for mobile and web dashboard clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

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
