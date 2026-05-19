import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import auth, location, messages, chats, user, ws
from app.core.redis import get_redis, close_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

LOG = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_redis()
    yield
    await close_redis()

app = FastAPI(title="Findr API", lifespan=lifespan)

app.include_router(auth.router,     prefix="/api/v1")
app.include_router(location.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(chats.router,    prefix="/api/v1")
app.include_router(user.router,     prefix="/api/v1")
app.include_router(ws.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
