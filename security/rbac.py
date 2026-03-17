#!/usr/bin/env python3
"""
Role-Based Access Control (RBAC) for Agent Tools
Defines capabilities for each agent role.
"""

from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from orchestrator.models import ToolCapability, AgentRole


@dataclass
class RolePermissions:
    """Permissions for a specific role."""
    role: AgentRole
    allowed_tools: set[ToolCapability] = field(default_factory=set)
    allowed_read_agents: set[int] = field(default_factory=set)
    allowed_write_agents: set[int] = field(default_factory=set)
    can_use_blackboard: bool = True
    can_whisper: bool = False
    can_trade: bool = False
    admin: bool = False


ROLE_PERMISSIONS: dict[AgentRole, RolePermissions] = {
    AgentRole.MAYOR: RolePermissions(
        role=AgentRole.MAYOR,
        allowed_tools={
            ToolCapability.MOVE,
            ToolCapability.TALK,
            ToolCapability.READ_MEMORY,
            ToolCapability.WRITE_MEMORY,
            ToolCapability.READ_BLACKBOARD,
            ToolCapability.WRITE_BLACKBOARD,
            ToolCapability.TRADE,
        },
        allowed_read_agents={1, 2, 3},
        allowed_write_agents={1, 2, 3},
        can_use_blackboard=True,
        can_whisper=True,
        can_trade=True,
        admin=True,
    ),
    AgentRole.MERCHANT: RolePermissions(
        role=AgentRole.MERCHANT,
        allowed_tools={
            ToolCapability.MOVE,
            ToolCapability.TALK,
            ToolCapability.READ_MEMORY,
            ToolCapability.WRITE_MEMORY,
            ToolCapability.READ_BLACKBOARD,
            ToolCapability.WRITE_BLACKBOARD,
            ToolCapability.TRADE,
            ToolCapability.INVENTORY,
        },
        allowed_read_agents={1, 2, 3},
        allowed_write_agents={1, 2},
        can_use_blackboard=True,
        can_whisper=False,
        can_trade=True,
    ),
    AgentRole.HERMIT: RolePermissions(
        role=AgentRole.HERMIT,
        allowed_tools={
            ToolCapability.MOVE,
            ToolCapability.TALK,
            ToolCapability.READ_MEMORY,
            ToolCapability.WRITE_MEMORY,
        },
        allowed_read_agents={3},
        allowed_write_agents={3},
        can_use_blackboard=False,
        can_whisper=False,
        can_trade=False,
    ),
    AgentRole.GUARD: RolePermissions(
        role=AgentRole.GUARD,
        allowed_tools={
            ToolCapability.MOVE,
            ToolCapability.TALK,
            ToolCapability.READ_MEMORY,
            ToolCapability.WRITE_MEMORY,
            ToolCapability.READ_BLACKBOARD,
            ToolCapability.WRITE_BLACKBOARD,
        },
        allowed_read_agents={1, 2, 3, 4},
        allowed_write_agents={1, 4},
        can_use_blackboard=True,
        can_whisper=True,
        can_trade=False,
    ),
    AgentRole.SPY: RolePermissions(
        role=AgentRole.SPY,
        allowed_tools={
            ToolCapability.MOVE,
            ToolCapability.TALK,
            ToolCapability.READ_MEMORY,
            ToolCapability.WRITE_MEMORY,
            ToolCapability.READ_BLACKBOARD,
            ToolCapability.WHISPER,
        },
        allowed_read_agents={1, 2, 3, 4, 5},
        allowed_write_agents={5},
        can_use_blackboard=True,
        can_whisper=True,
        can_trade=False,
    ),
}


class RBAC:
    """
    Role-Based Access Control for agent tools and actions.
    Enforces that agents can only use allowed capabilities.
    """
    
    def __init__(self):
        self.agent_roles: dict[int, AgentRole] = {}
        self.custom_permissions: dict[int, RolePermissions] = {}
        
    def assign_role(self, agent_id: int, role: AgentRole):
        """Assign a role to an agent."""
        self.agent_roles[agent_id] = role
    
    def get_role(self, agent_id: int) -> Optional[AgentRole]:
        """Get an agent's role."""
        return self.agent_roles.get(agent_id)
    
    def get_permissions(self, agent_id: int) -> Optional[RolePermissions]:
        """Get permissions for an agent."""
        if agent_id in self.custom_permissions:
            return self.custom_permissions[agent_id]
        
        role = self.agent_roles.get(agent_id)
        if role:
            return ROLE_PERMISSIONS.get(role)
        
        return None
    
    def can_use_tool(self, agent_id: int, tool: ToolCapability) -> bool:
        """Check if an agent can use a specific tool."""
        perms = self.get_permissions(agent_id)
        if not perms:
            return False
        return tool in perms.allowed_tools
    
    def can_read_agent(self, agent_id: int, target_agent_id: int) -> bool:
        """Check if an agent can read another agent's info."""
        perms = self.get_permissions(agent_id)
        if not perms:
            return False
        return target_agent_id in perms.allowed_read_agents
    
    def can_write_agent(self, agent_id: int, target_agent_id: int) -> bool:
        """Check if an agent can write to another agent's info."""
        perms = self.get_permissions(agent_id)
        if not perms:
            return False
        return target_agent_id in perms.allowed_write_agents
    
    def can_use_blackboard(self, agent_id: int) -> bool:
        """Check if an agent can use the blackboard."""
        perms = self.get_permissions(agent_id)
        if not perms:
            return False
        return perms.can_use_blackboard
    
    def can_whisper(self, agent_id: int) -> bool:
        """Check if an agent can send whisper messages."""
        perms = self.get_permissions(agent_id)
        if not perms:
            return False
        return perms.can_whisper
    
    def can_trade(self, agent_id: int) -> bool:
        """Check if an agent can trade."""
        perms = self.get_permissions(agent_id)
        if not perms:
            return False
        return perms.can_trade
    
    def is_admin(self, agent_id: int) -> bool:
        """Check if an agent has admin privileges."""
        perms = self.get_permissions(agent_id)
        if not perms:
            return False
        return perms.admin
    
    def set_custom_permissions(self, agent_id: int, permissions: RolePermissions):
        """Set custom permissions for an agent."""
        self.custom_permissions[agent_id] = permissions
    
    def enforce_tool_access(self, agent_id: int, tool: ToolCapability) -> tuple[bool, str]:
        """
        Enforce tool access and return (allowed, message).
        Use this before allowing an agent to use a tool.
        """
        if not self.can_use_tool(agent_id, tool):
            role = self.get_role(agent_id) or "unknown"
            return False, f"Agent {agent_id} (role: {role}) does not have permission to use {tool.value}"
        
        return True, "Access granted"
    
    def get_allowed_tools(self, agent_id: int) -> list[ToolCapability]:
        """Get list of tools an agent can use."""
        perms = self.get_permissions(agent_id)
        if not perms:
            return []
        return list(perms.allowed_tools)
