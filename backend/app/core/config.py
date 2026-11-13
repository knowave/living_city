from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "backend"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://ian@localhost:5432/living_city"
    DB_AUTO_SYNC: bool = True
    ENGINE_VERSION: str = "0.1.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
