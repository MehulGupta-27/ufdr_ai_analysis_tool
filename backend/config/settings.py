import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Database Configuration
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "ufdr_analysis")
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "root")
    
    # Qdrant Configuration
    qdrant_url: str = os.getenv("QDRANT_URL", "localhost:6333")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")
    
    # Neo4j Configuration
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "neo4j123")
    
    # Azure OpenAI Configuration
    embeddings_azure_endpoint: str = os.getenv("EMBEDDINGS_AZURE_ENDPOINT", "")
    embeddings_api_key: str = os.getenv("EMBEDDINGS_API_KEY", "")
    api_version: str = os.getenv("API_VERSION", "2024-08-01-preview")
    azure_embedding_model: str = os.getenv("AZURE_EMBEDDING_MODEL", "text-embedding-ada-002")
    azure_chat_model: str = os.getenv("AZURE_CHAT_MODEL", "gpt-4")
    
    # Gemini Configuration
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    
    # Redis Configuration
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD")
    
    # Application Configuration
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    class Config:
        env_file = ".env"

settings = Settings()