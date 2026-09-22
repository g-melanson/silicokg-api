from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Neo4j
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    # Security
    api_key: str

    # Query guard
    max_match_clauses: int = 10

    # Rate limiting
    rate_limit_per_minute: int = 30

    # CORS — set as JSON array in .env: CORS_ORIGINS='["http://localhost:3000"]'
    cors_origins: list[str] = []

    # Runtime environment
    api_env: str = "development"


settings = Settings()
