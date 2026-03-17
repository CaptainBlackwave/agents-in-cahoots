#!/usr/bin/env python3
"""
Circuit Breaker for Token & Cost Monitoring
"""

import os
import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from threading import Lock

from orchestrator.models import CircuitBreakerState, TokenUsage


TOKEN_PRICING = {
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-3.5-turbo": {"prompt": 0.001, "completion": 0.002},
    "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
    "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
}


@dataclass
class CircuitBreaker:
    """
    Circuit breaker that halts the system when token/cost limits are exceeded.
    """
    max_tokens: int = 100000
    max_cost: float = 10.0
    max_errors: int = 10
    
    state: CircuitBreakerState = field(default_factory=CircuitBreakerState)
    _lock: Lock = field(default_factory=Lock)
    
    def __post_init__(self):
        self.state = CircuitBreakerState(
            is_open=False,
            total_tokens=0,
            total_cost=0.0,
            request_count=0,
            error_count=0
        )
    
    def calculate_cost(self, model: str, usage: TokenUsage) -> float:
        """Calculate cost based on model and token usage."""
        pricing = TOKEN_PRICING.get(model, {"prompt": 0.001, "completion": 0.002})
        return (usage.prompt_tokens * pricing["prompt"] / 1000 + 
                usage.completion_tokens * pricing["completion"] / 1000)
    
    def record_request(self, model: str, usage: TokenUsage) -> bool:
        """
        Record a request and check if circuit should break.
        Returns True if request is allowed, False if circuit is open.
        """
        with self._lock:
            self.state.request_count += 1
            
            cost = self.calculate_cost(model, usage)
            self.state.total_cost += cost
            self.state.total_tokens += usage.total_tokens
            
            if self.should_break():
                self._open_circuit()
                return False
            
            return True
    
    def record_error(self, error: str):
        """Record an error and potentially open the circuit."""
        with self._lock:
            self.state.error_count += 1
            self.state.last_error = error
            
            if self.state.error_count >= self.max_errors:
                self._open_circuit()
    
    def should_break(self) -> bool:
        """Check if circuit should break."""
        return (self.state.total_tokens >= self.max_tokens or 
                self.state.total_cost >= self.max_cost or
                self.state.error_count >= self.max_errors)
    
    def _open_circuit(self):
        """Open the circuit breaker."""
        self.state.is_open = True
        self.state.opened_at = datetime.now().isoformat()
    
    def reset(self):
        """Reset the circuit breaker."""
        with self._lock:
            self.state = CircuitBreakerState()
    
    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "is_open": self.state.is_open,
            "total_tokens": self.state.total_tokens,
            "total_cost": self.state.total_cost,
            "request_count": self.state.request_count,
            "error_count": self.state.error_count,
            "last_error": self.state.last_error,
            "opened_at": self.state.opened_at,
            "limits": {
                "max_tokens": self.max_tokens,
                "max_cost": self.max_cost,
                "max_errors": self.max_errors
            }
        }
    
    def can_proceed(self) -> bool:
        """Check if requests can proceed."""
        return not self.state.is_open


class CostTracker:
    """Track and report costs across the simulation."""
    
    def __init__(self):
        self.total_cost = 0.0
        self.total_tokens = 0
        self.request_costs: list[dict] = []
        self._lock = Lock()
    
    def add_cost(self, model: str, usage: TokenUsage, cost: float):
        """Add a cost entry."""
        with self._lock:
            self.total_cost += cost
            self.total_tokens += usage.total_tokens
            self.request_costs.append({
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "tokens": usage.total_tokens,
                "cost": cost
            })
    
    def get_summary(self) -> dict:
        """Get cost summary."""
        with self._lock:
            return {
                "total_cost": self.total_cost,
                "total_tokens": self.total_tokens,
                "total_requests": len(self.request_costs),
                "avg_cost_per_request": self.total_cost / len(self.request_costs) if self.request_costs else 0,
                "avg_tokens_per_request": self.total_tokens / len(self.request_costs) if self.request_costs else 0
            }
    
    def get_breakdown(self) -> list[dict]:
        """Get detailed cost breakdown."""
        with self._lock:
            return self.request_costs.copy()
    
    def reset(self):
        """Reset the tracker."""
        with self._lock:
            self.total_cost = 0.0
            self.total_tokens = 0
            self.request_costs.clear()
