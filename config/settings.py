"""
Environment-aware settings for Streamline Government Refinance Agent.
Provides configuration classes for local and production environments.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BaseConfig:
    """Base configuration shared across all environments."""
    
    # Environment
    env: str = "local"
    debug: bool = True
    log_level: str = "INFO"
    
    # AWS / Bedrock
    aws_region: str = "us-east-1"
    bedrock_orchestrator_model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_specialist_model: str = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    bedrock_temperature: float = 0.3
    bedrock_guardrail_id: Optional[str] = None
    bedrock_guardrail_version: Optional[str] = None
    
    # Database type
    database_type: str = "postgres"


@dataclass
class LocalConfig(BaseConfig):
    """Configuration for local development environment."""
    
    env: str = "local"
    debug: bool = True
    
    # PostgreSQL
    database_type: str = "postgres"
    database_url: str = "postgresql://refiuser:localdev@localhost:5432/refi_agent"
    
    # MinIO (S3-compatible) - for document storage if needed
    storage_type: str = "minio"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "refi-documents"
    minio_secure: bool = False
    
    @classmethod
    def from_env(cls) -> "LocalConfig":
        """Create LocalConfig from environment variables."""
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            minio_endpoint=os.getenv("MINIO_ENDPOINT", cls.minio_endpoint),
            minio_access_key=os.getenv("MINIO_ACCESS_KEY", cls.minio_access_key),
            minio_secret_key=os.getenv("MINIO_SECRET_KEY", cls.minio_secret_key),
            minio_bucket=os.getenv("MINIO_BUCKET", cls.minio_bucket),
            minio_secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            bedrock_orchestrator_model=os.getenv("BEDROCK_ORCHESTRATOR_MODEL", cls.bedrock_orchestrator_model),
            bedrock_specialist_model=os.getenv("BEDROCK_SPECIALIST_MODEL", cls.bedrock_specialist_model),
            bedrock_temperature=float(os.getenv("BEDROCK_TEMPERATURE", cls.bedrock_temperature)),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            debug=os.getenv("DEBUG", "true").lower() == "true",
        )


@dataclass
class ProductionConfig(BaseConfig):
    """Configuration for production environment (AWS Bedrock AgentCore)."""
    
    env: str = "production"
    debug: bool = False
    log_level: str = "WARNING"
    
    # Hydra (production data platform)
    database_type: str = "hydra"
    hydra_endpoint: str = ""
    hydra_database: str = ""
    hydra_schema: str = ""
    
    # AWS S3
    storage_type: str = "s3"
    s3_bucket: str = "kind-lending-refi-documents"
    s3_region: str = "us-east-1"
    
    # Bedrock Guardrails (required in production)
    bedrock_guardrail_id: Optional[str] = None
    bedrock_guardrail_version: str = "1"
    
    @classmethod
    def from_env(cls) -> "ProductionConfig":
        """Create ProductionConfig from environment variables."""
        return cls(
            hydra_endpoint=os.getenv("HYDRA_ENDPOINT", ""),
            hydra_database=os.getenv("HYDRA_DATABASE", ""),
            hydra_schema=os.getenv("HYDRA_SCHEMA", ""),
            s3_bucket=os.getenv("S3_BUCKET", cls.s3_bucket),
            s3_region=os.getenv("S3_REGION", cls.s3_region),
            bedrock_orchestrator_model=os.getenv("BEDROCK_ORCHESTRATOR_MODEL", cls.bedrock_orchestrator_model),
            bedrock_specialist_model=os.getenv("BEDROCK_SPECIALIST_MODEL", cls.bedrock_specialist_model),
            bedrock_temperature=float(os.getenv("BEDROCK_TEMPERATURE", cls.bedrock_temperature)),
            bedrock_guardrail_id=os.getenv("BEDROCK_GUARDRAIL_ID"),
            bedrock_guardrail_version=os.getenv("BEDROCK_GUARDRAIL_VERSION", "1"),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
        )
