from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "backend"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://ian@localhost:5432/living_city"
    DB_AUTO_SYNC: bool = True
    ENGINE_VERSION: str = "0.1.0"
    WORLD_LOCK_TIMEOUT_MS: int = 5000
    RUNNER_ENABLED: bool = True
    RUNNER_TICK_INTERVAL_MS: int = 1000
    RUNNER_DISCOVERY_INTERVAL_MS: int = 1000
    RUNNER_BACKOFF_MAX_MS: int = 30000
    RUNNER_SHUTDOWN_TIMEOUT_MS: int = 10000
    SNAPSHOT_KEEP_LATEST: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
