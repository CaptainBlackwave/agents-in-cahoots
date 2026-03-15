#!/usr/bin/env python3
"""
Movement Engine for Agents in Cahoots
Allows agents to move within the 3x3 grid with bounds checking.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.db")

# Grid bounds (0-2 for both x and y)
GRID_MIN = 0
GRID_MAX = 2

# Direction mappings
DIRECTION_DELTAS = {
    "up": (0, -1),    # y decreases
    "down": (0, 1),   # y increases
    "left": (-1, 0),  # x decreases
    "right": (1, 0),  # x increases
}


def get_db_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


def get_agent(agent_id):
    """Retrieve agent details by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, current_x, current_y FROM agents WHERE id = ?", (agent_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            "id": result[0],
            "name": result[1],
            "x": result[2],
            "y": result[3]
        }
    return None


def move_agent(agent_id, direction):
    """
    Move an agent in the specified direction.
    
    Args:
        agent_id: The ID of the agent to move
        direction: One of 'up', 'down', 'left', 'right'
    
    Returns:
        dict: Result with 'success' boolean and 'message' string
    """
    # Validate direction
    direction = direction.lower()
    if direction not in DIRECTION_DELTAS:
        return {
            "success": False,
            "message": f"Invalid direction '{direction}'. Use: up, down, left, right"
        }
    
    # Get current agent position
    agent = get_agent(agent_id)
    if not agent:
        return {
            "success": False,
            "message": f"Agent with ID {agent_id} not found"
        }
    
    # Calculate new position
    delta_x, delta_y = DIRECTION_DELTAS[direction]
    new_x = agent["x"] + delta_x
    new_y = agent["y"] + delta_y
    
    # Bounds checking
    if new_x < GRID_MIN or new_x > GRID_MAX or new_y < GRID_MIN or new_y > GRID_MAX:
        # Get location name for the current position
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM locations WHERE x = ? AND y = ?", (agent["x"], agent["y"]))
        loc_result = cursor.fetchone()
        location_name = loc_result[0] if loc_result else "Unknown"
        conn.close()
        
        return {
            "success": False,
            "message": f"Cannot move {direction}: {agent['name']} is at the {location_name} (edge of the 3x3 grid)"
        }
    
    # Get location names for logging
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get old location name
    cursor.execute("SELECT name FROM locations WHERE x = ? AND y = ?", (agent["x"], agent["y"]))
    old_loc = cursor.fetchone()[0]
    
    # Get new location name
    cursor.execute("SELECT name FROM locations WHERE x = ? AND y = ?", (new_x, new_y))
    new_loc = cursor.fetchone()[0]
    
    # Update agent position
    cursor.execute(
        "UPDATE agents SET current_x = ?, current_y = ? WHERE id = ?",
        (new_x, new_y, agent_id)
    )
    
    # Log the movement
    timestamp = datetime.now().isoformat()
    detail = f"Moved {direction} from {old_loc} ({agent['x']},{agent['y']}) to {new_loc} ({new_x},{new_y})"
    cursor.execute(
        "INSERT INTO event_logs (timestamp, agent_id, action_type, detail) VALUES (?, ?, ?, ?)",
        (timestamp, agent_id, "MOVE", detail)
    )
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": f"{agent['name']} moved {direction} to {new_loc} ({new_x}, {new_y})",
        "old_position": (agent["x"], agent["y"]),
        "new_position": (new_x, new_y),
        "from_location": old_loc,
        "to_location": new_loc
    }


if __name__ == "__main__":
    # Test the movement engine
    print("=== Testing Movement Engine ===\n")
    
    # Test 1: Move agent 1 (The Mayor) right
    print("Test 1: Move The Mayor right")
    result = move_agent(1, "right")
    print(f"  Result: {result}\n")
    
    # Test 2: Move agent 1 (The Mayor) down
    print("Test 2: Move The Mayor down")
    result = move_agent(1, "down")
    print(f"  Result: {result}\n")
    
    # Test 3: Try invalid direction
    print("Test 3: Try invalid direction")
    result = move_agent(1, "diagonal")
    print(f"  Result: {result}\n")
    
    # Test 4: Try to move beyond bounds
    print("Test 4: Try to move beyond bounds (down from (1,2))")
    result = move_agent(1, "down")
    print(f"  Result: {result}\n")
    
    # Test 5: Non-existent agent
    print("Test 5: Non-existent agent")
    result = move_agent(999, "up")
    print(f"  Result: {result}\n")
    
    # Show event logs
    print("=== Event Logs ===")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, agent_id, action_type, detail FROM event_logs ORDER BY id")
    for row in cursor.fetchall():
        print(f"  {row}")
    conn.close()
