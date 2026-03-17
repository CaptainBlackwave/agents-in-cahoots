#!/usr/bin/env python3
"""
Tests for Agents in Cahoots
Golden state evaluations to ensure agent logic doesn't degrade.
"""

import pytest
import sqlite3
import os
import json
import tempfile
from datetime import datetime

from orchestrator.models import (
    AgentState, ActionType, ToolCapability, AgentRole,
    Agent, AgentAction, MessageVisibility
)
from orchestrator.state_machine import AgentStateMachine, Orchestrator
from orchestrator.circuit_breaker import CircuitBreaker, CostTracker
from security.rbac import RBAC, RolePermissions, ROLE_PERMISSIONS
from collaboration.blackboard import Blackboard
from testing.mock_environment import MockEnvironment, MockEnvironmentConfig, create_test_environment


TEST_DB_PATH = "test_game_state.db"


@pytest.fixture
def test_db():
    """Create a test database."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            persona_description TEXT,
            current_x INTEGER DEFAULT 1,
            current_y INTEGER DEFAULT 1
        )
    """)
    
    cursor.execute("""
        CREATE TABLE locations (
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            PRIMARY KEY (x, y)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_id INTEGER,
            action_type TEXT NOT NULL,
            detail TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE blackboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_agent_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            visibility TEXT DEFAULT 'public',
            created_at TEXT NOT NULL,
            tags TEXT
        )
    """)
    
    locations = [
        (0, 0, "Forest", "A forest"),
        (1, 1, "Town", "A town"),
        (2, 2, "Mountain", "A mountain"),
    ]
    cursor.executemany("INSERT INTO locations VALUES (?, ?, ?, ?)", locations)
    
    agents = [
        ("Alice", "A mayor", 1, 1),
        ("Bob", "A merchant", 1, 1),
        ("Charlie", "A hermit", 1, 1),
    ]
    cursor.executemany("INSERT INTO agents VALUES (?, ?, ?, ?)", agents)
    
    conn.commit()
    conn.close()
    
    yield TEST_DB_PATH
    
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


class TestStateMachine:
    """Tests for state machine."""
    
    def test_initial_state(self):
        machine = AgentStateMachine(agent_id=1)
        assert machine.get_state() == AgentState.IDLE
    
    def test_valid_transition(self):
        machine = AgentStateMachine(agent_id=1)
        assert machine.transition(AgentState.THINKING)
        assert machine.get_state() == AgentState.THINKING
    
    def test_invalid_transition(self):
        machine = AgentStateMachine(agent_id=1)
        assert not machine.transition(AgentState.TERMINATED)
        assert machine.get_state() == AgentState.IDLE
    
    def test_state_history(self):
        machine = AgentStateMachine(agent_id=1)
        machine.transition(AgentState.THINKING)
        machine.transition(AgentState.EXECUTING)
        
        history = machine.get_history()
        assert len(history) == 2
        assert history[0].to_state == AgentState.THINKING
        assert history[1].to_state == AgentState.EXECUTING
    
    def test_error_recovery(self):
        machine = AgentStateMachine(agent_id=1, max_retries=3)
        machine.transition(AgentState.THINKING)
        machine.transition(AgentState.ERROR, {"error": "test"})
        
        assert machine.error_count == 1
        assert machine.attempt_recovery()
        assert machine.get_state() == AgentState.IDLE


class TestOrchestrator:
    """Tests for orchestrator."""
    
    def test_register_agent(self):
        orchestrator = Orchestrator()
        machine = orchestrator.register_agent(1)
        assert machine.agent_id == 1
    
    def test_system_healthy(self):
        orchestrator = Orchestrator()
        orchestrator.register_agent(1)
        orchestrator.register_agent(2)
        
        assert orchestrator.is_system_healthy()
    
    def test_get_stuck_agents(self):
        orchestrator = Orchestrator()
        machine = orchestrator.register_agent(1)
        
        machine.transition(AgentState.THINKING)
        machine.transition(AgentState.ERROR)
        
        stuck = orchestrator.get_stuck_agents()
        assert 1 in stuck


class TestCircuitBreaker:
    """Tests for circuit breaker."""
    
    def test_initial_state(self):
        cb = CircuitBreaker(max_tokens=1000, max_cost=1.0)
        assert not cb.state.is_open
        assert cb.can_proceed()
    
    def test_token_limit(self):
        from orchestrator.models import TokenUsage
        
        cb = CircuitBreaker(max_tokens=100, max_cost=100.0)
        
        usage = TokenUsage(prompt_tokens=50, completion_tokens=60, total_tokens=110)
        assert not cb.record_request("gpt-3.5-turbo", usage)
        assert cb.state.is_open
    
    def test_cost_limit(self):
        from orchestrator.models import TokenUsage
        
        cb = CircuitBreaker(max_tokens=100000, max_cost=0.001)
        
        usage = TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200)
        assert not cb.record_request("gpt-3.5-turbo", usage)
        assert cb.state.is_open


class TestRBAC:
    """Tests for RBAC."""
    
    def test_assign_role(self):
        rbac = RBAC()
        rbac.assign_role(1, AgentRole.MAYOR)
        assert rbac.get_role(1) == AgentRole.MAYOR
    
    def test_can_use_tool(self):
        rbac = RBAC()
        rbac.assign_role(1, AgentRole.MAYOR)
        
        assert rbac.can_use_tool(1, ToolCapability.MOVE)
        assert rbac.can_use_tool(1, ToolCapability.TALK)
        assert not rbac.can_use_tool(3, ToolCapability.WRITE_BLACKBOARD)
    
    def test_hermit_restrictions(self):
        rbac = RBAC()
        rbac.assign_role(3, AgentRole.HERMIT)
        
        assert not rbac.can_use_blackboard(3)
        assert not rbac.can_whisper(3)


class TestBlackboard:
    """Tests for blackboard."""
    
    def test_post_and_read(self, test_db):
        bb = Blackboard(test_db)
        
        bb.post(1, "Test message", MessageVisibility.PUBLIC)
        
        entries = bb.read()
        assert len(entries) == 1
        assert entries[0].content == "Test message"
    
    def test_visibility_filter(self, test_db):
        bb = Blackboard(test_db)
        
        bb.post(1, "Public message", MessageVisibility.PUBLIC)
        bb.post(2, "Private message", MessageVisibility.PRIVATE)
        
        public_entries = bb.read()
        assert len(public_entries) == 1
        assert public_entries[0].content == "Public message"


class TestMockEnvironment:
    """Tests for mock environment."""
    
    def test_mock_response(self):
        env = create_test_environment()
        
        response = env.get_response("test prompt")
        assert response.content is not None
        assert "action" in response.content
    
    def test_error_simulation(self):
        config = MockEnvironmentConfig(enabled=True, error_rate=1.0)
        env = MockEnvironment(config)
        
        with pytest.raises(RuntimeError):
            env.get_response("test prompt")
    
    def test_stats(self):
        env = create_test_environment()
        
        env.get_response("test")
        env.get_response("test")
        
        stats = env.get_stats()
        assert stats["call_count"] == 2


class TestAgentAction:
    """Tests for agent action validation."""
    
    def test_valid_wait_action(self):
        action = AgentAction(action=ActionType.WAIT)
        success, message = action.execute()
        assert success
    
    def test_valid_move_action(self):
        from orchestrator.models import Direction
        action = AgentAction(action=ActionType.MOVE, direction=Direction.RIGHT)
        success, message = action.execute()
        assert success
    
    def test_move_without_direction(self):
        action = AgentAction(action=ActionType.MOVE)
        success, message = action.execute()
        assert not success
    
    def test_valid_talk_action(self):
        action = AgentAction(action=ActionType.TALK, dialogue="Hello!")
        success, message = action.execute()
        assert success


class TestCostTracker:
    """Tests for cost tracker."""
    
    def test_track_cost(self):
        from orchestrator.models import TokenUsage
        
        tracker = CostTracker()
        
        tracker.add_cost("gpt-3.5-turbo", TokenUsage(100, 100, 200), 0.001)
        
        summary = tracker.get_summary()
        assert summary["total_cost"] > 0
        assert summary["total_tokens"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
