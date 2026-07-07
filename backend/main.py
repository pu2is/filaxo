from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.engine import Engine

from modules.chat.router import router as chat_router
from modules.schema.domain_tables import DOMAIN_TABLES
from modules.schema.scope_tree import all_tables as scope_tree_tables
from shared.config import settings
from shared.db import engine as db_engine


def check_domain_tables_reachable(engine: Engine, domain_tables: dict[str, list[str]]) -> None:
    """Fail fast at startup (#25) if any funnel-scoped table is missing or unreachable --
    better a crash on boot than the first user's question dying with a cryptic 500."""
    tables = {table for tables in domain_tables.values() for table in tables}
    with engine.connect() as conn:
        for table in sorted(tables):
            conn.execute(text(f"SELECT TOP 0 * FROM {table}"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # DOMAIN_TABLES covers the live flat Wave-1 funnel; SCOPE_TREE extends the same
    # check (#30) to every table in either scope tree, since #31 hasn't wired the tree
    # into the funnel yet -- this is the only thing exercising those tables today.
    check_domain_tables_reachable(db_engine, {**DOMAIN_TABLES, "SCOPE_TREE": scope_tree_tables()})
    yield


app = FastAPI(title="Filax.One Backend", lifespan=lifespan)

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
