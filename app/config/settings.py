from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool
    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # External Medical LLM Configuration
    MEDICAL_LLM_URL: str = "http://127.0.0.1:8000"
    MEDICAL_LLM_ENDPOINT: str = "/ask"
    MEDICAL_LLM_MODEL: str = "openbiollm"
    MEDICAL_LLM_TIMEOUT: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()