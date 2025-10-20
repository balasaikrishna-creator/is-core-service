from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # AI / Third-Party APIs
    GOOGLE_GEMINI_API_KEY: str
    GOOGLE_MAPS_API_KEY: str

    # Payment (Braintree/PayPal)
    BRAINTREE_MERCHANT_ID: str
    BRAINTREE_PUBLIC_KEY: str
    BRAINTREE_PRIVATE_KEY: str

    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    DEBUG: bool = True

    class Config:
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        env_file_encoding = "utf-8"

settings = Settings()
