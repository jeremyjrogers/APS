from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://aps:aps@localhost:5432/aps"
    api_title: str = "APS Planning API"
    # Comma-separated list of allowed frontend origins for CORS. Defaults to
    # the local Vite dev server; set to the deployed frontend's URL in prod.
    cors_origins: str = "http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Render (and Heroku-style hosts) hand out "postgres://..." or plain
        # "postgresql://..." — SQLAlchemy rejects the former outright and the
        # latter only works by accident of whatever driver happens to be
        # installed. Pin the dialect explicitly so it's never ambiguous.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg2://" + v[len("postgresql://"):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        # Defensive scheme normalization, same reasoning as the frontend's
        # API_BASE: Render's cross-service env reference may hand us a bare
        # hostname rather than a full origin.
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return [o if o.startswith(("http://", "https://")) else f"https://{o}" for o in origins]


settings = Settings()
