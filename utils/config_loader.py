"""
Environment-aware configuration loader.
Switches between local and production configurations based on ENV variable.
"""

import os
from functools import lru_cache
from typing import Union

from dotenv import load_dotenv

from config.settings import LocalConfig, ProductionConfig


# Load environment variables from .env file
load_dotenv()


@lru_cache(maxsize=1)
def get_config() -> Union[LocalConfig, ProductionConfig]:
    """
    Get the configuration for the current environment.
    Uses ENV environment variable to determine which config to load.
    
    Returns:
        LocalConfig or ProductionConfig based on ENV variable
    """
    env = os.getenv("ENV", "local").lower()
    
    if env == "production" or env == "prod":
        config = ProductionConfig.from_env()
        print(f"[Config] Loaded PRODUCTION configuration")
    else:
        config = LocalConfig.from_env()
        print(f"[Config] Loaded LOCAL configuration")
    
    return config


def get_database_config() -> dict:
    """Get database-specific configuration."""
    config = get_config()
    
    if config.database_type == "postgres":
        return {
            "type": "postgres",
            "url": config.database_url,
        }
    else:
        return {
            "type": "hydra",
            "endpoint": config.hydra_endpoint,
            "database": config.hydra_database,
            "schema": config.hydra_schema,
        }


def get_storage_config() -> dict:
    """Get storage-specific configuration."""
    config = get_config()
    
    if config.storage_type == "minio":
        return {
            "type": "minio",
            "endpoint": config.minio_endpoint,
            "access_key": config.minio_access_key,
            "secret_key": config.minio_secret_key,
            "bucket": config.minio_bucket,
            "secure": config.minio_secure,
        }
    else:
        return {
            "type": "s3",
            "bucket": config.s3_bucket,
            "region": config.s3_region,
        }


def get_model_config() -> dict:
    """Get Bedrock model configuration."""
    config = get_config()
    
    model_config = {
        "orchestrator_model": config.bedrock_orchestrator_model,
        "specialist_model": config.bedrock_specialist_model,
        "temperature": config.bedrock_temperature,
        "region": config.aws_region,
    }
    
    # Add guardrails if configured (production)
    if config.bedrock_guardrail_id:
        model_config["guardrail_id"] = config.bedrock_guardrail_id
        model_config["guardrail_version"] = config.bedrock_guardrail_version
    
    return model_config


def is_local() -> bool:
    """Check if running in local environment."""
    return get_config().env == "local"


def is_production() -> bool:
    """Check if running in production environment."""
    return get_config().env == "production"
