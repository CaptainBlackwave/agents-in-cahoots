#!/usr/bin/env python3
"""
Shared Blackboard for Agent Communication
Allows agents to post and read information like a team workspace.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field
from threading import Lock

from orchestrator.models import BlackboardEntry, MessageVisibility


class Blackboard:
    """
    Shared workspace where agents can post and read information.
    Supports different visibility levels.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = Lock()
        
    def _get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def post(self, author_agent_id: int, content: str, 
             visibility: MessageVisibility = MessageVisibility.PUBLIC,
             tags: Optional[list[str]] = None) -> int:
        """Post a new entry to the blackboard."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO blackboard (author_agent_id, content, visibility, tags, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (author_agent_id, content, visibility.value, 
                  json.dumps(tags or []), timestamp))
            
            entry_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return entry_id
    
    def read(self, agent_id: Optional[int] = None, 
             visibility: Optional[MessageVisibility] = None,
             tags: Optional[list[str]] = None, limit: int = 50) -> list[BlackboardEntry]:
        """Read blackboard entries visible to an agent."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT id, author_agent_id, content, visibility, created_at, updated_at, tags
            FROM blackboard
            WHERE 1=1
        """
        params = []
        
        if visibility:
            query += " AND (visibility = ? OR visibility = ?)"
            params.extend([MessageVisibility.PUBLIC.value, visibility.value])
        else:
            query += " AND visibility = ?"
            params.append(MessageVisibility.PUBLIC.value)
        
        if agent_id:
            query += " AND (visibility = ? OR author_agent_id = ?)"
            params.extend([MessageVisibility.PUBLIC.value, agent_id])
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        entries = []
        for row in cursor.fetchall():
            entry_tags = json.loads(row[6]) if row[6] else []
            
            if tags:
                if not any(t in entry_tags for t in tags):
                    continue
            
            entries.append(BlackboardEntry(
                id=row[0],
                author_agent_id=row[1],
                content=row[2],
                visibility=MessageVisibility(row[3]),
                created_at=row[4],
                updated_at=row[5],
                tags=entry_tags
            ))
        
        conn.close()
        return entries
    
    def update(self, entry_id: int, agent_id: int, new_content: str) -> bool:
        """Update an entry (only author can edit)."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT author_agent_id FROM blackboard WHERE id = ?
            """, (entry_id,))
            
            result = cursor.fetchone()
            if not result or result[0] != agent_id:
                conn.close()
                return False
            
            cursor.execute("""
                UPDATE blackboard 
                SET content = ?, updated_at = ?
                WHERE id = ?
            """, (new_content, datetime.now().isoformat(), entry_id))
            
            conn.commit()
            conn.close()
            return True
    
    def delete(self, entry_id: int, agent_id: int) -> bool:
        """Delete an entry (only author can delete)."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT author_agent_id FROM blackboard WHERE id = ?
            """, (entry_id,))
            
            result = cursor.fetchone()
            if not result or result[0] != agent_id:
                conn.close()
                return False
            
            cursor.execute("DELETE FROM blackboard WHERE id = ?", (entry_id,))
            
            conn.commit()
            conn.close()
            return True
    
    def search(self, query: str, agent_id: Optional[int] = None) -> list[BlackboardEntry]:
        """Search blackboard entries by content."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        search_query = """
            SELECT id, author_agent_id, content, visibility, created_at, updated_at, tags
            FROM blackboard
            WHERE content LIKE ? AND (visibility = ? OR author_agent_id = ?)
            ORDER BY created_at DESC
            LIMIT 100
        """
        
        pattern = f"%{query}%"
        params = [pattern, MessageVisibility.PUBLIC.value]
        
        if agent_id:
            params.append(agent_id)
        else:
            params.append(-1)
        
        cursor.execute(search_query, params)
        
        entries = []
        for row in cursor.fetchall():
            entries.append(BlackboardEntry(
                id=row[0],
                author_agent_id=row[1],
                content=row[2],
                visibility=MessageVisibility(row[3]),
                created_at=row[4],
                updated_at=row[5],
                tags=json.loads(row[6]) if row[6] else []
            ))
        
        conn.close()
        return entries


def init_blackboard_table(db_path: str):
    """Initialize the blackboard table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blackboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_agent_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            visibility TEXT DEFAULT 'public',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            tags TEXT,
            FOREIGN KEY (author_agent_id) REFERENCES agents(id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_blackboard_visibility
        ON blackboard(visibility)
    """)
    
    conn.commit()
    conn.close()
