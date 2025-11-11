from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from src.agents.orchestrator import orchestrator


router = APIRouter()


@router.get("/status")
async def get_agents_status():
    """Get status of all registered agents."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="System not ready")
    
    return {
        "orchestrator": {
            "status": "active",
            "name": orchestrator.name,
            "agents_registered": list(orchestrator.agents.keys())
        },
        "agents": {
            phase: {
                "name": agent.name,
                "status": "registered"
            }
            for phase, agent in orchestrator.agents.items()
        }
    }


@router.get("/metrics")
async def get_agents_metrics():
    """Get performance metrics for agents."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="System not ready")
    
    # Get coordination metrics
    metrics = await orchestrator.get_coordination_metrics()
    
    return {
        "metrics": metrics,
        "timestamp": "2025-01-11T00:00:00Z"  # Would use actual timestamp
    }


@router.post("/register")
async def register_agent(agent_info: Dict[str, Any]):
    """Register a new agent (for testing and development)."""
    # This is a placeholder for dynamic agent registration
    # In a real implementation, this would be more sophisticated
    return {
        "message": "Agent registration not implemented in this version",
        "received_info": agent_info
    }


@router.get("/workflow/rules")
async def get_workflow_rules():
    """Get current workflow coordination rules."""
    if not orchestrator or not orchestrator.coordination_manager:
        raise HTTPException(status_code=503, detail="System not ready")
    
    rules = []
    for rule in orchestrator.coordination_manager.coordination_flow.rules:
        rules.append({
            "trigger_event": rule.trigger_event.value,
            "source_phase": rule.source_phase.value,
            "target_phase": rule.target_phase.value if rule.target_phase else None,
            "priority": rule.priority,
            "timeout_seconds": rule.timeout_seconds
        })
    
    return {
        "rules": rules,
        "total_count": len(rules)
    }