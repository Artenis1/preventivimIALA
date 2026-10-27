from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .config import get_settings
from .db import engine
from .auth import router as auth_router
from .prices import router as prices_router

settings = get_settings()
app = FastAPI(title="SmartEstimate AI", version="1.0.0")
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(
                {"detail": "Cross-site request rejected"}, status_code=403
            )
        if (
            origin
            and origin not in origins
            and origin != str(request.base_url).rstrip("/")
        ):
            return JSONResponse({"detail": "Origin rejected"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM users LIMIT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            {"status": "database unavailable or migrations required"}, status_code=503
        )


app.include_router(auth_router, prefix="/api")
app.include_router(prices_router, prefix="/api")

from .projects import router as projects_router

app.include_router(projects_router, prefix="/api")


@app.exception_handler(ValueError)
async def invalid_value(request: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)[:1000]}, status_code=422)
