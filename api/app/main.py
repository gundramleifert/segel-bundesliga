import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.jobs import jobs
from app.live import hub
from app.problems import CONTENT_TYPE, Problem, http_problem_body, problem_handler
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
    waivers,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    # Cancel running optimizations cleanly instead of cutting them off mid-run, and end
    # every open live stream — otherwise the server waits on them before it stops.
    await jobs.shutdown()
    await hub.shutdown()


def _operation_id(route: APIRoute) -> str:
    """The function's own name as the operation id.

    FastAPI's default appends path and verb — `list_series_api_series_get` — which is
    unique but unreadable, and the frontend client is **generated from these names**
    (`orval`, see `web/orval.config.ts`): they become `useListSeriesApiSeriesGet` in every
    component. The handler names are already unique across all routers, and a duplicate
    would be caught immediately, because FastAPI refuses to build the schema twice under
    one id.
    """
    return route.name


app = FastAPI(
    lifespan=lifespan,
    generate_unique_id_function=_operation_id,
    # The association runs several series and the 1. Segel-Bundesliga is only one of them,
    # so neither the title nor the description may carry that name (see CLAUDE.md).
    title="Deutsche Segel-Liga API",
    version="0.1.0",
    description=(
        "Backend for the Deutsche Segel-Liga website: master data, standings, pairing "
        "lists. Points are never stored, only computed from raw results."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Every error response is RFC 9457 application/problem+json. Typed errors (app.problems)
# carry a stable `type` the frontend maps to a translation; plain HTTPExceptions and
# validation errors get a generic type but keep `detail` where clients already read it.
app.add_exception_handler(Problem, problem_handler)


@app.exception_handler(StarletteHTTPException)
async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=http_problem_body(exc.status_code, exc.detail, request.url.path),
        headers=getattr(exc, "headers", None),
        media_type=CONTENT_TYPE,
    )


@app.exception_handler(RequestValidationError)
async def _validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "type": "/errors/validation",
            "title": "Request could not be processed",
            "status": 422,
            "instance": request.url.path,
            # The per-field list stays under `detail` — the frontend already renders it.
            "detail": jsonable_encoder(exc.errors()),
        },
        media_type=CONTENT_TYPE,
    )


# sailors.me_router before public.router: both define a route under /api/sailors, and
# Starlette matches by registration order — "/api/sailors/me" must be tried before
# public.router's "/api/sailors/{sailor_id}", or "me" would be parsed as a sailor id.
app.include_router(sailors.me_router)
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(events.router)
app.include_router(clubs.router)
# Same prefix as clubs.router, but without its admin/editor-only router dependency —
# the crest is also a club manager's own business (Story V-3).
app.include_router(clubs.crest_router)
app.include_router(crew.router)
app.include_router(series.router)
app.include_router(applications.router)
app.include_router(club_members.router)
app.include_router(sailors.router)
app.include_router(waivers.router)

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
