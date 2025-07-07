# config.py
from pydantic import BaseSettings, Field, HttpUrl

class Settings(BaseSettings):
    tg_token: str = Field(..., env="TG_TOKEN")
    django_url: HttpUrl = Field(..., env="DJANGO_URL")
    django_key: str = Field(None, env="DJANGO_KEY")
    api_url: HttpUrl = Field(..., env="API_URL")
    max_size_mb: int = Field(5, env="MAX_SIZE_MB")

    class Config:
        env_file = ".env"   # Solo en desarrollo

settings = Settings()
