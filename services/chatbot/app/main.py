"""
Yastubo — Service: Chatbot
Port: 8007

Facade para integración con SofIA (n8n + Chatwoot).
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from common.config import settings

from .controllers.chatbot_controller import router as chatbot_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from common.database import engine

    await engine.dispose()


app = FastAPI(
    title="Yastubo — Chatbot",
    version="1.0.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(chatbot_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "chatbot"}
