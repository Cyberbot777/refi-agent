"""
Configuration module for Streamline Government Refinance Agent.
"""

from config.settings import LocalConfig, ProductionConfig, BaseConfig
from config.mip_rates import MIP_RATES, get_mip_rate

__all__ = [
    "LocalConfig",
    "ProductionConfig", 
    "BaseConfig",
    "MIP_RATES",
    "get_mip_rate",
]
