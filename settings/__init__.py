from datetime import timedelta

from pydantic_settings import BaseSettings
from pydantic import computed_field,Field
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    # DB
    DB_USERNAME: str = "postgres"
    DB_PASSWORD: str = "1234"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "hr_system"
    JWT_SECRET_KEY: str = "sdfesfsefsfhe"
    JWT_ACCESS_TOKEN_EXPIRES : timedelta = timedelta(days=365)
    JWT_REFRESH_TOKEN_EXPIRES :timedelta = timedelta(days=365)
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    INVITE_EXPIRE: int = 60*60*24*2
    MAIL_USERNAME: str = Field(..., validation_alias="MAIL_USERNAME")
    MAIL_PASSWORD: str = Field(..., validation_alias="MAIL_PASSWORD")
    MAIL_FROM: str = Field(..., validation_alias="MAIL_USERNAME")
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.qq.com"
    MAIL_FROM_NAME: str = "Reed"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg://{self.DB_USERNAME}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
