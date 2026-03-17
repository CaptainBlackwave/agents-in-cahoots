#!/usr/bin/env python3
"""
Secret Channels for Private Agent Communication
Supports game-theory style secret messaging (e.g., The Traitors, Werewolf).
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from threading import Lock

from orchestrator.models import SecretMessage, AgentRole


class SecretChannel:
    """
    Private messaging system for agents.
    Supports public, private, and secret (faction-only) messages.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = Lock()
        self.agent_factions: dict[int, Optional[str]] = {}
        
    def _get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def set_faction(self, agent_id: int, faction: Optional[str]):
        """Assign an agent to a faction (for secret channel routing)."""
        self.agent_factions[agent_id] = faction
    
    def send_message(self, from_agent_id: int, to_agent_id: int, 
                    content: str, is_secret: bool = False) -> int:
        """
        Send a private message to another agent.
        If is_secret=True, only faction members can see it.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO secret_messages 
                (from_agent_id, to_agent_id, content, is_secret, created_at, read)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (from_agent_id, to_agent_id, content, 1 if is_secret else 0, timestamp))
            
            message_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return message_id
    
    def receive_messages(self, agent_id: int, unread_only: bool = True) -> list[SecretMessage]:
        """Get messages sent to an agent."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT id, from_agent_id, to_agent_id, content, is_secret, created_at, read
            FROM secret_messages
            WHERE to_agent_id = ?
        """
        
        if unread_only:
            query += " AND read = 0"
        
        query += " ORDER BY created_at DESC LIMIT 50"
        
        cursor.execute(query, (agent_id,))
        
        messages = []
        for row in cursor.fetchall():
            messages.append(SecretMessage(
                id=row[0],
                from_agent_id=row[1],
                to_agent_id=row[2],
                content=row[3],
                created_at=row[5],
                read=bool(row[6])
            ))
        
        conn.close()
        return messages
    
    def mark_read(self, message_id: int, agent_id: int) -> bool:
        """Mark a message as read."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE secret_messages 
                SET read = 1 
                WHERE id = ? AND to_agent_id = ?
            """, (message_id, agent_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            return success
    
    def get_faction_messages(self, agent_id: int) -> list[SecretMessage]:
        """Get all secret messages for the agent's faction."""
        faction = self.agent_factions.get(agent_id)
        if not faction:
            return []
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, from_agent_id, to_agent_id, content, is_secret, created_at, read
            FROM secret_messages
            WHERE is_secret = 1 AND to_agent_id IN (
                SELECT id FROM agents WHERE faction = ?
            )
            ORDER BY created_at DESC
            LIMIT 50
        """, (faction,))
        
        messages = []
        for row in cursor.fetchall():
            messages.append(SecretMessage(
                id=row[0],
                from_agent_id=row[1],
                to_agent_id=row[2],
                content=row[3],
                created_at=row[5],
                read=bool(row[6])
            ))
        
        conn.close()
        return messages
    
    def broadcast_to_faction(self, from_agent_id: int, content: str) -> int:
        """Broadcast a message to all faction members."""
        faction = self.agent_factions.get(from_agent_id)
        if not faction:
            return 0
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM agents WHERE faction = ? AND id != ?
        """, (faction, from_agent_id))
        
        members = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        count = 0
        for member_id in members:
            self.send_message(from_agent_id, member_id, content, is_secret=True)
            count += 1
        
        return count


def init_secret_channels_table(db_path: str):
    """Initialize secret messages table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS secret_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent_id INTEGER NOT NULL,
            to_agent_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_secret INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            read INTEGER DEFAULT 0,
            FOREIGN KEY (from_agent_id) REFERENCES agents(id),
            FOREIGN KEY (to_agent_id) REFERENCES agents(id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_secret_messages_recipient
        ON secret_messages(to_agent_id, read)
    """)
    
    conn.commit()
    conn.close()
