"""LLMProvider seam (mvp-request D1): swapping models/providers later is a config change,
not a rewrite. OllamaProvider is the MVP1 implementation (local 7B, zero API cost)."""

from typing import Literal, Protocol

import httpx
from pydantic import BaseModel

from shared.config import settings
from shared.prompts import build_generate_sql_prompt, build_ranking_params_prompt


class SqlGenResult(BaseModel):
    sql: str | None = None
    explanation: str | None = None
    error: str | None = None


class RankingParams(BaseModel):
    sort_column: str | None = None
    direction: Literal["ASC", "DESC"] | None = None
    n: int | None = None


class LLMProvider(Protocol):
    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        few_shots: list[str],
        last_error: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> SqlGenResult: ...

    async def extract_ranking_params(self, question: str, schema_context: str) -> RankingParams: ...


class OllamaProvider:
    def __init__(self, model: str | None = None, host: str | None = None):
        self._model = model or settings.llm_sql_model or settings.llm_model
        self._host = host or settings.ollama_host

    async def _generate_json(self, prompt: str, schema: dict) -> dict:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._host}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "format": schema,
                    "stream": False,
                    "options": {"temperature": 0, "num_ctx": 4096},
                },
            )
            response.raise_for_status()
            return response.json()

    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        few_shots: list[str],
        last_error: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> SqlGenResult:
        prompt = build_generate_sql_prompt(question, schema_context, few_shots, last_error, date_from, date_to)
        body = await self._generate_json(prompt, SqlGenResult.model_json_schema())
        return SqlGenResult.model_validate_json(body["response"])

    async def extract_ranking_params(self, question: str, schema_context: str) -> RankingParams:
        prompt = build_ranking_params_prompt(question, schema_context)
        body = await self._generate_json(prompt, RankingParams.model_json_schema())
        return RankingParams.model_validate_json(body["response"])
