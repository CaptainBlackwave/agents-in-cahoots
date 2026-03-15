#!/usr/bin/env python3
"""
SQLite Database Setup for Agents in Cahoots
Initializes the game state database with tables and seed data.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.db")

def init_database():
    """Initialize the database with tables and seed data."""
    
    # Remove existing database if it exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create agents table
    cursor.execute("""
        CREATE TABLE agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            persona_description TEXT,
            current_x INTEGER DEFAULT 1,
            current_y INTEGER DEFAULT 1
        )
    """)
    print("Created 'agents' table")
    
    # Create locations table
    cursor.execute("""
        CREATE TABLE locations (
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            PRIMARY KEY (x, y)
        )
    """)
    print("Created 'locations' table")
    
    # Create event_logs table
    cursor.execute("""
        CREATE TABLE event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_id INTEGER,
            action_type TEXT NOT NULL,
            detail TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)
    print("Created 'event_logs' table")
    
    # Seed 3x3 grid of locations
    locations = [
        (0, 0, "Forest Clearing", "A quiet clearing surrounded by ancient trees."),
        (0, 1, "River Bank", "The gentle sound of flowing water."),
        (0, 2, "Mountain Path", "A winding path leading up the mountain."),
        (1, 0, "Village Square", "The heart of the village where villagers gather."),
        (1, 1, "Town Center", "The central hub with a marketplace and well."),
        (1, 2, "Crossroads", "A busy intersection where travelers meet."),
        (2, 0, "Old Mill", "An abandoned mill creaking in the wind."),
        (2, 1, "Farming Fields", "Golden wheat fields stretching to the horizon."),
        (2, 2, "Cave Entrance", "A dark cave mouth leading into the unknown."),
    ]
    
    cursor.executemany(
        "INSERT INTO locations (x, y, name, description) VALUES (?, ?, ?, ?)",
        locations
    )
    print(f"Seeded {len(locations)} locations (3x3 grid)")
    
    # Create 3 basic agents
    agents = [
        ("The Mayor", "A respected leader who governs the village with wisdom and fairness.", 1, 1),
        ("The Merchant", "A cunning trader who knows the value of everything.", 1, 1),
        ("The Hermit", "A mysterious sage who lives in solitude, seeking ancient knowledge.", 1, 1),
    ]
    
    cursor.executemany(
        "INSERT INTO agents (name, persona_description, current_x, current_y) VALUES (?, ?, ?, ?)",
        agents
    )
    print(f"Seeded {len(agents)} agents: {', '.join(a[0] for a in agents)}")
    
    # Log initial setup event
    cursor.execute(
        "INSERT INTO event_logs (timestamp, agent_id, action_type, detail) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(), None, "SYSTEM", "Database initialized")
    )
    print("Logged system initialization event")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Database setup complete: {DB_PATH}")
    print(f"   - 3 tables created")
    print(f"   - 9 locations seeded")
    print(f"   - 3 agents created")
    
    return DB_PATH


if __name__ == "__main__":
    init_database()
