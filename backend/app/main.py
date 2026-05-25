import os

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, entities, events, export, extractions, files, import_, mcp_intent, people, relationships, search, self_, settings, stages, timeline


def create_app() -> FastAPI:
    app = FastAPI(title="Dossier API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):[0-9]+$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(people.router)
    app.include_router(entities.router)
    app.include_router(relationships.router)
    app.include_router(events.router)
    app.include_router(stages.router)
    app.include_router(self_.router)
    app.include_router(search.router)
    app.include_router(files.router)
    app.include_router(settings.router)
    app.include_router(chat.router)
    app.include_router(extractions.router)
    app.include_router(timeline.router)
    app.include_router(import_.router)
    app.include_router(export.router)
    app.include_router(mcp_intent.router)

    @app.exception_handler(HTTPException)
    def http_exception_handler(_, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": str(exc.detail)})

    @app.exception_handler(RequestValidationError)
    def validation_exception_handler(_, exc: RequestValidationError):
        messages = []
        for error in exc.errors():
            location = ".".join(str(item) for item in error.get("loc", []))
            messages.append(f"{location}: {error.get('msg')}")
        return JSONResponse(status_code=422, content={"ok": False, "error": "; ".join(messages)})

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app


def _cors_origins() -> list[str]:
    origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    origins.extend(origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip())
    return origins


app = create_app()
