#!/usr/bin/env python3
"""
Hierarchical Memory System for Agents in Cahoots
Short-term and Long-term memory with vector storage.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from orchestrator.models import Memory


class MemoryType(str, Enum):
    """Types of memory."""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    WORKING = "working"


class MemoryPriority(str, Enum):
    """Memory importance levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ShortTermMemory:
    """Agent's short-term memory (current task context)."""
    max_items: int = 10
    items: list[dict] = field(default_factory=list)
    
    def add(self, content: str, metadata: Optional[dict] = None):
        """Add an item to short-term memory."""
        self.items.append({
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        })
        if len(self.items) > self.max_items:
            self.items.pop(0)
    
    def get_recent(self, n: int = 5) -> list[dict]:
        """Get the n most recent items."""
        return self.items[-n:]
    
    def clear(self):
        """Clear short-term memory."""
        self.items.clear()
    
    def consolidate(self) -> list[str]:
        """Consolidate short-term memories for transfer to long-term."""
        return [item["content"] for item in self.items]


class HierarchicalMemory:
    """
    Hierarchical memory system with short-term and long-term storage.
    Uses vector database for semantic retrieval of long-term memories.
    """
    
    def __init__(self, agent_id: int, db_path: str, vector_store=None):
        self.agent_id = agent_id
        self.db_path = db_path
        self.short_term = ShortTermMemory()
        self.long_term_enabled = vector_store is not None
        self.vector_store = vector_store
        
    def add_memory(self, content: str, memory_type: MemoryType = MemoryType.SHORT_TERM,
                   priority: MemoryPriority = MemoryPriority.MEDIUM, metadata: Optional[dict] = None):
        """Add a memory to the appropriate storage."""
        if memory_type == MemoryType.SHORT_TERM:
            self.short_term.add(content, metadata)
        elif memory_type == MemoryType.LONG_TERM:
            self._store_long_term(content, priority, metadata)
        elif memory_type == MemoryType.WORKING:
            self.short_term.add(content, {**(metadata or {}), "type": "working"})
    
    def _store_long_term(self, content: str, priority: MemoryPriority, metadata: Optional[dict]):
        """Store in long-term memory (vector DB)."""
        if not self.long_term_enabled:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO agent_memories 
            (agent_id, content, memory_type, priority, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            self.agent_id,
            content,
            MemoryType.LONG_TERM.value,
            priority.value,
            datetime.now().isoformat(),
            json.dumps(metadata or {})
        ))
        
        memory_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        if self.vector_store:
            self.vector_store.store_memory(self.agent_id, content)
    
    def recall(self, query: str, limit: int = 5) -> list[dict]:
        """
        Recall relevant memories using semantic search.
        Combines short-term and long-term retrieval.
        """
        results = []
        
        short_term_results = self.short_term.get_recent(limit)
        results.extend([{**item, "source": "short_term"} for item in short_term_results])
        
        if self.long_term_enabled and self.vector_store:
            long_term_results = self.vector_store.retrieve_memories(
                self.agent_id, query, limit
            )
            results.extend([{
                "content": r["text_content"],
                "timestamp": r["timestamp"],
                "similarity": r.get("similarity", 0),
                "source": "long_term"
            } for r in long_term_results])
        
        results.sort(key=lambda x: x.get("similarity", 1), reverse=True)
        return results[:limit]
    
    def get_context_for_prompt(self, max_items: int = 5) -> str:
        """Generate context string for LLM prompt."""
        memories = self.short_term.get_recent(max_items)
        
        if not memories:
            return "No recent memories."
        
        context = "## Recent Memories\n"
        for mem in memories:
            context += f"- {mem['content']}\n"
        
        return context
    
    def consolidate_to_long_term(self):
        """Transfer important short-term memories to long-term storage."""
        to_consolidate = self.short_term.consolidate()
        
        for content in to_consolidate:
            self._store_long_term(content, MemoryPriority.MEDIUM, {"consolidated": True})
        
        self.short_term.clear()
    
    def get_all_long_term(self, limit: int = 100) -> list[dict]:
        """Get all long-term memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, content, memory_type, priority, created_at
            FROM agent_memories
            WHERE agent_id = ? AND memory_type = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (self.agent_id, MemoryType.LONG_TERM.value, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "content": row[1],
                "type": row[2],
                "priority": row[3],
                "timestamp": row[4]
            })
        
        conn.close()
        return results


def init_memory_tables(db_path: str):
    """Initialize memory tables in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            priority INTEGER DEFAULT 2,
            created_at TEXT NOT NULL,
            last_accessed TEXT,
            access_count INTEGER DEFAULT 0,
            metadata TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_agent_type
        ON agent_memories(agent_id, memory_type)
    """)
    
    conn.commit()
    conn.close()
