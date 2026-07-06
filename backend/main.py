from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from modules.chat.router import router as chat_router
from shared.config import settings

app = FastAPI(title="Filax.One Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
