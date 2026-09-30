from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://aps:aps@localhost:5432/aps"
    api_title: str = "APS Planning API"


settings = Settings()
