from fastapi import FastAPI

app = FastAPI(title="Filax.One Backend")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
