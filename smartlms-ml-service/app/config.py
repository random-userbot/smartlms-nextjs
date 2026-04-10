from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/smartlms"
    
    # AWS / SQS / S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    SQS_QUEUE_URL: str = "" # Set in production
    SQS_WAIT_TIME_SECONDS: int = 20
    SQS_MAX_MESSAGES: int = 10
    
    AWS_S3_MODEL_BUCKET: str = "" # Set in production
    MODEL_S3_PREFIX: str = "models/" # Folder in S3
    
    # ML
    MODEL_ID_DEFAULT: str = "builtin::xgboost" # Default to builtin if exports missing

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
