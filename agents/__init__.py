"""
Agents module for Streamline Government Refinance system.
Implements the multi-agent architecture using Strands SDK "agents as tools" pattern.
"""

from agents.refi_orchestrator import create_orchestrator, get_orchestrator, process_refinance
from agents.package_validator import package_validator
from agents.program_router import program_router
from agents.eligibility_checker import eligibility_checker
from agents.seasoning_validator import seasoning_validator
from agents.ntb_calculator import ntb_calculator
from agents.recoupment_analyzer import recoupment_analyzer
from agents.refi_decision_agent import refi_decision_agent

__all__ = [
    # Orchestrator
    "create_orchestrator",
    "get_orchestrator",
    "process_refinance",
    # Specialist agents (as tools)
    "package_validator",
    "program_router",
    "eligibility_checker",
    "seasoning_validator",
    "ntb_calculator",
    "recoupment_analyzer",
    "refi_decision_agent",
]
