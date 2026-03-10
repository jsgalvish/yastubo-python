from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.app_debug,
)


@app.get("/")
def root():
    return {"status": "ok", "app": settings.app_name}
