#!/usr/bin/env python3
"""
Pydantic Models for Agents in Cahoots
Provides structured output validation and type safety.
"""

from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import json


class AgentState(str, Enum):
    """Agent execution states."""
    IDLE = "IDLE"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    ERROR = "ERROR"
    TERMINATED = "TERMINATED"


class ActionType(str, Enum):
    """Valid action types for agents."""
    MOVE = "move"
    TALK = "talk"
    WAIT = "wait"
    WHISPER = "whisper"
    USE_TOOL = "use_tool"
    READ_BLACKBOARD = "read_blackboard"
    WRITE_BLACKBOARD = "write_blackboard"


class Direction(str, Enum):
    """Valid movement directions."""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class ToolCapability(str, Enum):
    """Available tool capabilities."""
    MOVE = "move"
    TALK = "talk"
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    READ_BLACKBOARD = "read_blackboard"
    WRITE_BLACKBOARD = "write_blackboard"
    WHISPER = "whisper"
    TRADE = "trade"
    INVENTORY = "inventory"


class AgentRole(str, Enum):
    """Agent roles for RBAC."""
    MAYOR = "mayor"
    MERCHANT = "merchant"
    HERMIT = "hermit"
    GUARD = "guard"
    SPY = "spy"


class MessageVisibility(str, Enum):
    """Message visibility levels."""
    PUBLIC = "public"
    PRIVATE = "private"
    SECRET = "secret"


class StateTransition(BaseModel):
    """Record of a state transition."""
    agent_id: int
    from_state: AgentState
    to_state: AgentState
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Position(BaseModel):
    """2D position on the grid."""
    x: int = Field(ge=0, le=2)
    y: int = Field(ge=0, le=2)
    
    def to_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)


class Agent(BaseModel):
    """Agent model with validation."""
    id: int
    name: str = Field(min_length=1, max_length=100)
    persona_description: str = Field(max_length=1000)
    current_x: int = Field(ge=0, le=2)
    current_y: int = Field(ge=0, le=2)
    role: AgentRole = AgentRole.MAYOR
    capabilities: list[ToolCapability] = Field(default_factory=list)
    
    @property
    def position(self) -> Position:
        return Position(x=self.current_x, y=self.current_y)
    
    def has_capability(self, cap: ToolCapability) -> bool:
        return cap in self.capabilities


class AgentAction(BaseModel):
    """Structured action output from an agent."""
    action: ActionType
    direction: Optional[Direction] = None
    dialogue: Optional[str] = Field(default=None, max_length=500)
    target_agent_id: Optional[int] = None
    tool_name: Optional[str] = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        if not v:
            raise ValueError("Action cannot be empty")
        return v
    
    def execute(self) -> tuple[bool, str]:
        """Execute the action and return (success, message)."""
        if self.action == ActionType.WAIT:
            return True, "Agent waited"
        elif self.action == ActionType.MOVE:
            if not self.direction:
                return False, "Move action requires direction"
            return True, f"Moving {self.direction.value}"
        elif self.action == ActionType.TALK:
            if not self.dialogue:
                return False, "Talk action requires dialogue"
            return True, f"Said: {self.dialogue}"
        elif self.action == ActionType.WHISPER:
            if not self.target_agent_id:
                return False, "Whisper action requires target_agent_id"
            return True, f"Whispered to agent {self.target_agent_id}"
        return False, f"Unknown action: {self.action}"


class Location(BaseModel):
    """Location model."""
    x: int
    y: int
    name: str
    description: Optional[str] = None


class Memory(BaseModel):
    """Memory entry with metadata."""
    id: Optional[int] = None
    agent_id: int
    timestamp: str
    text_content: str
    embedding: Optional[list[float]] = None
    importance: float = Field(default=1.0, ge=0.0, le=1.0)
    memory_type: str = "episodic"


class BlackboardEntry(BaseModel):
    """Entry on the shared blackboard."""
    id: Optional[int] = None
    author_agent_id: int
    content: str = Field(max_length=2000)
    visibility: MessageVisibility = MessageVisibility.PUBLIC
    created_at: str
    updated_at: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class SecretMessage(BaseModel):
    """Secret message for private communication."""
    id: Optional[int] = None
    from_agent_id: int
    to_agent_id: int
    content: str = Field(max_length=1000)
    created_at: str
    read: bool = False


class TokenUsage(BaseModel):
    """Token usage tracking."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def total(self) -> int:
        return self.total_tokens


class CircuitBreakerState(BaseModel):
    """Circuit breaker state tracking."""
    is_open: bool = False
    total_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    opened_at: Optional[str] = None
    
    def should_break(self, max_tokens: int, max_cost: float) -> bool:
        if self.is_open:
            return True
        return self.total_tokens >= max_tokens or self.total_cost >= max_cost


class TraceEvent(BaseModel):
    """Trace event for debugging."""
    timestamp: str
    agent_id: int
    event_type: str
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[float] = None


class HumanFeedback(BaseModel):
    """Human feedback for HITL."""
    agent_id: int
    approved: bool
    feedback: Optional[str] = None
    modified_action: Optional[AgentAction] = None
    timestamp: str


class MockEnvironmentConfig(BaseModel):
    """Configuration for mock environment."""
    enabled: bool = True
    mock_llm_responses: list[dict[str, Any]] = Field(default_factory=list)
    simulate_latency: bool = False
    latency_ms: int = 100
    error_rate: float = 0.0
