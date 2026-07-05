from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5-coder:7b"
    llm_sql_model: str | None = None
    llm_narrate_model: str | None = None
    ollama_host: str = "http://localhost:11434"

    # Database (read-only application login, see docker/create-readonly-user.sql)
    db_server: str = "localhost,14330"
    db_name: str = "FilaksOne"
    db_user: str = "filaks_readonly"
    db_password: str = ""
    db_driver: str = "ODBC Driver 18 for SQL Server"

    # CORS - Vite dev server default port
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
