#!/usr/bin/env python3
"""
Mock Environment for Testing
Allows testing without burning LLM credits.
"""

import os
import json
import random
import time
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from orchestrator.models import MockEnvironmentConfig, AgentAction, ActionType, Direction


class MockLLMResponse:
    """Mock LLM response for testing."""
    def __init__(self, content: str, tokens: int = 100):
        self.content = content
        self.tokens = tokens
        self.prompt_tokens = tokens // 3
        self.completion_tokens = tokens * 2 // 3


DEFAULT_MOCK_RESPONSES = {
    "move": '{"action": "move", "direction": "right"}',
    "talk": '{"action": "talk", "dialogue": "Hello, fellow agents!"}',
    "wait": '{"action": "wait"}',
    "whisper": '{"action": "whisper", "target_agent_id": 2, "dialogue": "Secret message"}',
}


class MockEnvironment:
    """
    Mock environment for testing agent logic without LLM API calls.
    """
    
    def __init__(self, config: Optional[MockEnvironmentConfig] = None):
        self.config = config or MockEnvironmentConfig()
        self.call_count = 0
        self.total_latency = 0
        self.error_count = 0
        self.response_history: list[dict] = []
        
    def should_error(self) -> bool:
        """Determine if this call should simulate an error."""
        return random.random() < self.config.error_rate
    
    def get_response(self, prompt: str, action_hint: Optional[str] = None) -> MockLLMResponse:
        """Get a mock LLM response."""
        if not self.config.enabled:
            raise RuntimeError("Mock environment is not enabled")
        
        if self.should_error():
            self.error_count += 1
            raise RuntimeError("Simulated API error")
        
        self.call_count += 1
        
        if self.config.mock_llm_responses:
            response = random.choice(self.config.mock_llm_responses)
            return MockLLMResponse(
                content=response.get("content", '{"action": "wait"}'),
                tokens=response.get("tokens", 100)
            )
        
        action = action_hint or random.choice(["move", "talk", "wait"])
        content = DEFAULT_MOCK_RESPONSES.get(action, '{"action": "wait"}')
        
        if self.config.simulate_latency:
            time.sleep(self.config.latency_ms / 1000)
            self.total_latency += self.config.latency_ms
        
        self.response_history.append({
            "timestamp": datetime.now().isoformat(),
            "prompt_preview": prompt[:50],
            "response": content
        })
        
        return MockLLMResponse(content)
    
    def add_mock_response(self, content: str, tokens: int = 100):
        """Add a custom mock response."""
        self.config.mock_llm_responses.append({
            "content": content,
            "tokens": tokens
        })
    
    def get_stats(self) -> dict:
        """Get mock environment statistics."""
        return {
            "enabled": self.config.enabled,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "total_latency_ms": self.total_latency,
            "avg_latency_ms": self.total_latency / self.call_count if self.call_count > 0 else 0,
            "error_rate": self.error_count / self.call_count if self.call_count > 0 else 0,
            "response_count": len(self.config.mock_llm_responses)
        }
    
    def reset_stats(self):
        """Reset call statistics."""
        self.call_count = 0
        self.total_latency = 0
        self.error_count = 0
        self.response_history.clear()


class EnvironmentMocker:
    """
    Context manager for mocking external services.
    """
    
    def __init__(self, mock_env: MockEnvironment):
        self.mock_env = mock_env
        self.original_urlopen = None
        
    def __enter__(self):
        import urllib.request
        self.original_urlopen = urllib.request.urlopen
        
        def mock_urlopen(request, timeout=None):
            if hasattr(request, 'full_url') and 'api.openai.com' in request.full_url:
                response = self.mock_env.get_response("mock prompt")
                
                class MockResponse:
                    def __init__(self, content):
                        self._content = content
                    
                    def read(self):
                        return json.dumps({
                            "choices": [{
                                "message": {
                                    "content": response.content
                                }
                            }]
                        }).encode('utf-8')
                
                return MockResponse(response)
            
            return self.original_urlopen(request, timeout)
        
        import urllib.request
        urllib.request.urlopen = mock_urlopen
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import urllib.request
        if self.original_urlopen:
            urllib.request.urlopen = self.original_urlopen


def create_test_environment(error_rate: float = 0.0, 
                           latency_ms: int = 100) -> MockEnvironment:
    """Create a configured mock environment for testing."""
    config = MockEnvironmentConfig(
        enabled=True,
        error_rate=error_rate,
        simulate_latency=True,
        latency_ms=latency_ms
    )
    return MockEnvironment(config)
