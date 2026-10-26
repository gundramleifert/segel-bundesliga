import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth import requires_sign_in
from app.config import settings
from app.jobs import jobs
from app.live import hub
from app.problems import (
    CONTENT_TYPE,
    Operation,
    Problem,
    declare_problems,
    http_problem_body,
    problem_handler,
)
from app.routers import (
    admin,
    announcements,
    applications,
    auth,
    club_members,
    clubs,
    crew,
    dev,
    events,
    expenses,
    guardians,
    me,
    media,
    payments,
    people,
    personal,
    posts,
    public,
    series,
    tracking,
    waivers,
)
from app.tracking.service import position_publisher


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    # Cancel running optimizations cleanly instead of cutting them off mid-run, and end
    # every open live stream — otherwise the server waits on them before it stops.
    await jobs.shutdown()
    await position_publisher.shutdown()
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
async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
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


# sailors.me_router before public.router: both define a route under /api/people, and
# Starlette matches by registration order — "/api/people/me" must be tried before
# public.router's "/api/people/{person_id}", or "me" would be parsed as a sailor id.
app.include_router(people.me_router)
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(events.router)
app.include_router(clubs.router)
# Same prefix as clubs.router, but without its admin/editor-only router dependency —
# the crest is also a team manager's own business (Story V-3).
app.include_router(clubs.crest_router)
app.include_router(crew.router)
app.include_router(announcements.router)
app.include_router(series.router)
app.include_router(applications.router)
app.include_router(club_members.router)
app.include_router(people.router)
app.include_router(waivers.router)
app.include_router(guardians.router)
app.include_router(personal.router)
app.include_router(me.router)
app.include_router(expenses.router)
app.include_router(payments.router)
app.include_router(tracking.router)
app.include_router(tracking.admin_router)
app.include_router(posts.router)
app.include_router(posts.admin_router)
app.include_router(media.admin_router)
app.include_router(media.import_router)
app.include_router(media.public_router)

if settings.dev_login:
    # Development only: login without verification to try out roles.
    logging.getLogger(__name__).warning(
        "SBL_DEV_LOGIN is active — /api/dev issues tokens without verification. "
        "Disable this in any reachable environment."
    )
    app.include_router(dev.router)


_default_openapi = app.openapi


def _openapi_with_problems() -> dict:
    """The OpenAPI document, with the problem responses each operation can give
    (``app.problems.declare_problems``) — so the generated client and ``/docs`` show
    ``application/problem+json`` rather than only FastAPI's validation error."""
    schema = _default_openapi()
    if not schema.get("x-problems-declared"):
        declare_problems(
            schema,
            (
                Operation(route.path, method, requires_sign_in(route.dependant))
                for route in iter_route_contexts(app.routes)
                if getattr(route, "dependant", None) is not None
                for method in route.methods or ()
            ),
        )
        schema["x-problems-declared"] = True
    return schema


app.openapi = _openapi_with_problems


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
            "matchday": "/api/events/{event_id}",
            "pairing_list": "/api/events/{event_id}/pairing",
            "league_year": "/api/leagues/{slug}?year={year}",
            "series_table": "/api/series/{series_id}/table",
            "login_methods": "/api/auth/providers",
        },
    }


@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
