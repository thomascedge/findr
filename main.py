from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import auth, location, messages, chats

app = FastAPI(title="Findr API")

app.include_router(auth.router,     prefix="/api/v1")
app.include_router(location.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(chats.router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}
