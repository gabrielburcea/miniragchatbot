from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    jwt_secret: str = "change-me-in-env"


    # LLM - Groq, free tier, Llama 3.3 70B

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    # For embeddigns - local, free, CPU friendly 
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Vector DB 
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "policy_docs"

settings = Settings()