import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.jobs import jobs
from app.routers import (
    admin,
    applications,
    auth,
    club_members,
    clubs,
    crew,
    dev,
    events,
    public,
    sailors,
    series,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    # Cancel running optimizations cleanly instead of cutting them off mid-run.
    await jobs.shutdown()


app = FastAPI(
    lifespan=lifespan,
    title="Sailing Bundesliga API",
    version="0.1.0",
    description=(
        "Backend for the Sailing Bundesliga website: master data, standings, pairing lists. "
        "Points are never stored, only computed from raw results."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(events.router)
app.include_router(clubs.router)
app.include_router(crew.router)
app.include_router(series.router)
app.include_router(applications.router)
app.include_router(club_members.router)
app.include_router(sailors.router)

if settings.dev_login:
    # Development only: login without verification to try out roles.
    logging.getLogger(__name__).warning(
        "SBL_DEV_LOGIN is active — /api/dev issues tokens without verification. "
        "Disable this in any reachable environment."
    )
    app.include_router(dev.router)


@app.get("/", tags=["operations"], summary="Entry point")
async def index() -> dict[str, object]:
    """Signpost instead of a bare 404.

    This is just the API — the website is a separate frontend. When someone calls the root
    in a browser, they should see where to go next.
    """
    return {
        "name": app.title,
        "version": app.version,
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "endpoints": {
            "clubs": "/api/clubs",
            "leagues": "/api/leagues",
            "events": "/api/events",
            "matchday": "/api/events/{slug}",
            "pairing_list": "/api/events/{slug}/pairing",
            "league_table": "/api/leagues/{slug}/table/{year}",
            "login_methods": "/api/auth/providers",
        },
    }


@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
