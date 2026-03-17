#!/usr/bin/env python3
"""
State Machine Orchestrator for Agents in Cahoots
Manages agent transitions between states with robust error handling.
"""

import asyncio
from enum import Enum
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

from pydantic import BaseModel, Field
from orchestrator.models import AgentState, StateTransition, AgentAction


class AgentStateMachine:
    """
    State machine for managing agent states and transitions.
    Prevents infinite loops and handles failures gracefully.
    """
    
    VALID_TRANSITIONS: dict[AgentState, list[AgentState]] = {
        AgentState.IDLE: [AgentState.THINKING, AgentState.WAITING],
        AgentState.THINKING: [AgentState.EXECUTING, AgentState.ERROR, AgentState.IDLE],
        AgentState.EXECUTING: [AgentState.IDLE, AgentState.WAITING, AgentState.ERROR],
        AgentState.WAITING: [AgentState.IDLE, AgentState.THINKING],
        AgentState.ERROR: [AgentState.IDLE, AgentState.TERMINATED],
        AgentState.TERMINATED: [],
    }
    
    def __init__(self, agent_id: int, max_retries: int = 3):
        self.agent_id = agent_id
        self.current_state = AgentState.IDLE
        self.state_history: list[StateTransition] = []
        self.retry_count = 0
        self.max_retries = max_retries
        self.error_count = 0
        self.max_errors = 5
        
    def can_transition(self, new_state: AgentState) -> bool:
        """Check if transition to new_state is valid."""
        return new_state in self.VALID_TRANSITIONS.get(self.current_state, [])
    
    def transition(self, new_state: AgentState, metadata: Optional[dict] = None) -> bool:
        """
        Attempt to transition to a new state.
        Returns True if successful, False otherwise.
        """
        if not self.can_transition(new_state):
            self._log_transition(AgentState.ERROR, success=False, 
                               error=f"Invalid transition: {self.current_state} -> {new_state}")
            return False
        
        old_state = self.current_state
        self.current_state = new_state
        
        transition_record = StateTransition(
            agent_id=self.agent_id,
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        self.state_history.append(transition_record)
        
        if new_state == AgentState.ERROR:
            self.error_count += 1
        elif new_state == AgentState.IDLE:
            self.retry_count = 0
            
        return True
    
    def _log_transition(self, state: AgentState, success: bool, error: Optional[str] = None):
        """Internal method to log state transitions."""
        metadata = {"success": success}
        if error:
            metadata["error"] = error
        self.transition(state, metadata)
    
    def attempt_recovery(self) -> bool:
        """Attempt to recover from error state."""
        if self.error_count >= self.max_errors:
            self.transition(AgentState.TERMINATED, {"reason": "max_errors_exceeded"})
            return False
        
        if self.retry_count >= self.max_retries:
            self.transition(AgentState.TERMINATED, {"reason": "max_retries_exceeded"})
            return False
        
        self.retry_count += 1
        return self.transition(AgentState.IDLE, {"recovery_attempt": self.retry_count})
    
    def get_state(self) -> AgentState:
        """Get current state."""
        return self.current_state
    
    def is_terminal(self) -> bool:
        """Check if agent is in a terminal state."""
        return self.current_state in [AgentState.TERMINATED, AgentState.ERROR]
    
    def get_history(self) -> list[StateTransition]:
        """Get state transition history."""
        return self.state_history.copy()
    
    def reset(self):
        """Reset the state machine."""
        self.current_state = AgentState.IDLE
        self.state_history.clear()
        self.retry_count = 0
        self.error_count = 0


class Orchestrator:
    """
    Orchestrates multiple agents using state machines.
    Manages coordination and prevents system-wide failures.
    """
    
    def __init__(self, max_concurrent: int = 5):
        self.agents: dict[int, AgentStateMachine] = {}
        self.max_concurrent = max_concurrent
        self.global_state = AgentState.IDLE
        self.execution_order: list[int] = []
        
    def register_agent(self, agent_id: int) -> AgentStateMachine:
        """Register a new agent with the orchestrator."""
        if agent_id not in self.agents:
            self.agents[agent_id] = AgentStateMachine(agent_id)
        return self.agents[agent_id]
    
    def get_agent_machine(self, agent_id: int) -> Optional[AgentStateMachine]:
        """Get the state machine for an agent."""
        return self.agents.get(agent_id)
    
    def execute_agent(self, agent_id: int, action: AgentAction) -> tuple[bool, str]:
        """
        Execute an action for an agent, managing state transitions.
        Returns (success, message).
        """
        machine = self.get_agent_machine(agent_id)
        if not machine:
            return False, f"Agent {agent_id} not registered"
        
        if machine.is_terminal():
            return False, f"Agent {agent_id} is in terminal state: {machine.get_state()}"
        
        if not machine.transition(AgentState.THINKING, {"action": action.action}):
            return False, f"Failed to transition to THINKING state"
        
        success, message = action.execute()
        
        if success:
            machine.transition(AgentState.EXECUTING, {"result": message})
            machine.transition(AgentState.IDLE)
        else:
            machine.transition(AgentState.ERROR, {"error": message})
            machine.attempt_recovery()
        
        return success, message
    
    def get_all_states(self) -> dict[int, AgentState]:
        """Get current state of all agents."""
        return {agent_id: machine.get_state() 
                for agent_id, machine in self.agents.items()}
    
    def is_system_healthy(self) -> bool:
        """Check if the system is healthy (no agents in error/terminated)."""
        return all(not machine.is_terminal() 
                  for machine in self.agents.values())
    
    def get_stuck_agents(self) -> list[int]:
        """Get agents that may be stuck (in error state)."""
        return [agent_id for agent_id, machine in self.agents.items() 
                if machine.current_state == AgentState.ERROR]
    
    def force_reset_agent(self, agent_id: int) -> bool:
        """Force reset an agent to IDLE state."""
        machine = self.agents.get(agent_id)
        if machine:
            machine.reset()
            return True
        return False
    
    def get_execution_stats(self) -> dict[str, Any]:
        """Get execution statistics for all agents."""
        total_transitions = sum(len(m.state_history) for m in self.agents.values())
        return {
            "total_agents": len(self.agents),
            "healthy_agents": len([m for m in self.agents.values() if not m.is_terminal()]),
            "stuck_agents": len(self.get_stuck_agents()),
            "total_transitions": total_transitions,
            "states": self.get_all_states()
        }
