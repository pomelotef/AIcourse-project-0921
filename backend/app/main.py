from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import live  # noqa: F401  (registers the ORM hooks that drive live refresh)
from .routers import actions, ai_summary, auth, goals, live as live_router, me, meetings, projects, timeline, updates

app = FastAPI(title="LabPulse API", version="0.1.0")

for r in (auth, projects, goals, updates, actions, meetings, ai_summary, timeline, me, live_router):
    app.include_router(r.router)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    # Keep FastAPI's structured errors, but also give the UI one readable message.
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "輸入"
    msg = str(first.get("msg", "格式不正確")).removeprefix("Value error, ")
    return JSONResponse(status_code=422, content={"detail": f"{field}：{msg}", "errors": jsonable(errors)})


def jsonable(errors):
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(errors, custom_encoder={Exception: str})


@app.get("/api/health")
def health():
    return {"ok": True}
