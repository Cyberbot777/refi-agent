"""
Refi Orchestrator Agent
Main entry point that coordinates all specialist agents using the agents-as-tools pattern.
Routes queries to specialists and synthesizes responses for FHA Streamline and VA IRRRL.
"""

from strands import Agent
from strands.models import BedrockModel

from config.prompts import ORCHESTRATOR_PROMPT
from utils.config_loader import get_model_config

# Import agent tools (agents wrapped as tools)
from agents.package_validator import package_validator
from agents.program_router import program_router
from agents.eligibility_checker import eligibility_checker
from agents.seasoning_validator import seasoning_validator
from agents.ntb_calculator import ntb_calculator
from agents.recoupment_analyzer import recoupment_analyzer
from agents.refi_decision_agent import refi_decision_agent


def create_orchestrator() -> Agent:
    """
    Create and configure the Refi Orchestrator agent.
    Uses Sonnet for better reasoning and synthesis.
    """
    model_config = get_model_config()
    
    model = BedrockModel(
        model_id=model_config["orchestrator_model"],
        temperature=model_config["temperature"],
    )
    
    # Agents wrapped as tools - sequential for smooth streaming
    orchestrator = Agent(
        model=model,
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[
            package_validator,
            program_router,
            eligibility_checker,
            seasoning_validator,
            ntb_calculator,
            recoupment_analyzer,
            refi_decision_agent,
        ]
    )
    
    return orchestrator


# Singleton orchestrator instance
_orchestrator = None


def get_orchestrator() -> Agent:
    """Get or create the Orchestrator agent (singleton)."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_orchestrator()
    return _orchestrator


def process_refinance(message: str) -> str:
    """
    Process a refinance application inquiry.
    
    Args:
        message: The user's message or inquiry (e.g., "Process REFI-001")
        
    Returns:
        The orchestrator's response
    """
    orchestrator = get_orchestrator()
    response = orchestrator(message)
    return str(response)
