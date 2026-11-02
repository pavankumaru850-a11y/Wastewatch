"""main.py -- FastAPI application entrypoint."""
import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()  # must run before app modules read os.environ

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .database import SessionLocal  # noqa: E402
from .migrate import run_migrations  # noqa: E402
from .routers import (admin, analytics, auth, dashboard, detection, duplicates, hotspots, notifications,  # noqa: E402
                      reports, staff, sync, training, users, waste_types)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("wastewatch")

DEV = os.environ.get("APP_ENV", "development") != "production"
app = FastAPI(title="WasteWatch API", version="2.0.0",
              docs_url="/docs" if DEV else None, redoc_url="/redoc" if DEV else None,
              openapi_url="/openapi.json" if DEV else None)

cors_origins = os.environ.get("CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cors_origins == "*" else [o.strip() for o in cors_origins.split(",")],
    allow_credentials=cors_origins != "*",  # browsers reject credentials with wildcard origin
    allow_methods=["*"], allow_headers=["*"],
)

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

for r in (auth, users, detection, reports, admin, staff, dashboard, training, waste_types,
          hotspots, duplicates, notifications, analytics, sync):
    app.include_router(r.router)

# WasteWatch decides waste / not-waste only; one generic type is kept for the legacy waste_types table.
DEFAULT_WASTE_TYPES = ["waste"]


@app.on_event("startup")
def on_startup():
    from .utils.security import SECRET_KEY, validate_secret
    warning = validate_secret(os.environ.get("APP_ENV", "development"), SECRET_KEY)
    if warning:
        log.warning(warning)
    added = run_migrations()
    if added:
        log.info("database upgraded: %d column(s) added", len(added))
    from .models import ModelVersion, WasteType
    from . import detector
    from .services import training_service
    db = SessionLocal()
    try:
        # Restore the model an admin activated (survives restarts); loaded lazily on first use.
        active = db.query(ModelVersion).filter(ModelVersion.deployed == True).first()  # noqa: E712
        if active and os.path.exists(active.path):
            detector.set_active(active.path, active.version)
            log.info("active AI model: %s", active.version)
        elif detector.MODEL_PATH.exists():
            dep = training_service.get_current_deployed_model()
            detector.set_active(str(detector.MODEL_PATH), dep["version"] if dep else None)
        # Add any default type that is missing (also upgrades existing databases); never touches existing rows.
        existing = {n for (n,) in db.query(WasteType.name).all()}
        missing = [n for n in DEFAULT_WASTE_TYPES if n not in existing]
        for name in missing:
            db.add(WasteType(name=name, label=name.replace("_", " ").title(), is_active=True))
        if missing:
            db.commit()
    finally:
        db.close()


@app.middleware("http")
async def request_log(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        log.exception("unhandled error %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"success": False, "detail": "Something went wrong. Please try again."})
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, (time.time() - start) * 1000)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc: RequestValidationError):
    fields = [".".join(str(p) for p in e["loc"] if p != "body") + ": " + e["msg"] for e in exc.errors()]
    return JSONResponse(status_code=422, content={"success": False, "detail": "Invalid input. " + "; ".join(fields)})


@app.get("/api/health", tags=["system"])
def api_health():
    return {"status": "healthy"}


@app.get("/", tags=["system"])
def health():
    return {"status": "ok", "service": "WasteWatch API", "version": app.version}
