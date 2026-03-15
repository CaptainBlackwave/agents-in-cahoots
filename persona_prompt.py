#!/usr/bin/env python3
"""
Persona Prompt Wrapper for Agents in Cahoots
Generates system prompts that dictate agent behavior based on persona and context.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.db")

# Grid bounds for calculating nearby agents (Manhattan distance)
GRID_SIZE = 3
NEARBY_DISTANCE = 1  # Include agents within 1 tile


def get_db_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


def get_agent(agent_id):
    """Retrieve full agent details by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, persona_description, current_x, current_y FROM agents WHERE id = ?",
        (agent_id,)
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            "id": result[0],
            "name": result[1],
            "persona_description": result[2],
            "x": result[3],
            "y": result[4]
        }
    return None


def get_location(x, y):
    """Get location details by coordinates."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, description FROM locations WHERE x = ? AND y = ?", (x, y))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            "name": result[0],
            "description": result[1]
        }
    return None


def get_nearby_agents(agent_id, x, y, max_distance=NEARBY_DISTANCE):
    """Get agents within specified Manhattan distance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all other agents
    cursor.execute(
        "SELECT id, name, current_x, current_y FROM agents WHERE id != ?",
        (agent_id,)
    )
    all_agents = cursor.fetchall()
    conn.close()
    
    nearby = []
    for agent in all_agents:
        distance = abs(agent[2] - x) + abs(agent[3] - y)
        if distance <= max_distance:
            location = get_location(agent[2], agent[3])
            nearby.append({
                "id": agent[0],
                "name": agent[1],
                "x": agent[2],
                "y": agent[3],
                "distance": distance,
                "location": location["name"] if location else "Unknown"
            })
    
    # Sort by distance
    nearby.sort(key=lambda a: a["distance"])
    return nearby


def retrieve_memories(agent_id, limit=5):
    """
    Retrieve relevant past context for an agent from event_logs.
    
    Args:
        agent_id: The ID of the agent to retrieve memories for
        limit: Maximum number of memories to retrieve (default 5)
    
    Returns:
        list: List of memory dictionaries with timestamp, action_type, and detail
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the most recent events for this agent
    cursor.execute("""
        SELECT timestamp, action_type, detail 
        FROM event_logs 
        WHERE agent_id = ? 
        ORDER BY id DESC 
        LIMIT ?
    """, (agent_id, limit))
    
    memories = []
    for row in cursor.fetchall():
        memories.append({
            "timestamp": row[0],
            "action_type": row[1],
            "detail": row[2]
        })
    
    conn.close()
    return memories


def generate_agent_prompt(agent_id):
    """
    Generate a fully constructed system prompt for an agent.
    
    This function builds a prompt that:
    - Enforces the agent's persona
    - Includes current location and nearby agents
    - Provides relevant past context (memories)
    - Instructs the LLM to return a JSON object with action and dialogue
    
    Args:
        agent_id: The ID of the agent to generate a prompt for
    
    Returns:
        str: A fully constructed system prompt
    
    Raises:
        ValueError: If the agent with given ID doesn't exist
    """
    # Fetch agent details
    agent = get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")
    
    # Fetch current location
    location = get_location(agent["x"], agent["y"])
    location_info = f"{location['name']}: {location['description']}" if location else "Unknown location"
    
    # Fetch nearby agents
    nearby_agents = get_nearby_agents(agent_id, agent["x"], agent["y"])
    
    # Retrieve relevant memories
    memories = retrieve_memories(agent_id)
    
    # Build the system prompt
    prompt = f"""You are playing as {agent['name']}.

## Your Persona
{agent['persona_description']}

## Current Location
You are at: {location_info}
Coordinates: ({agent['x']}, {agent['y']})

## Nearby Agents
"""
    
    if nearby_agents:
        for i, nearby in enumerate(nearby_agents, 1):
            prompt += f"{i}. {nearby['name']} - {nearby['location']} (distance: {nearby['distance']})\n"
    else:
        prompt += "You are alone.\n"
    
    # Add memories section
    prompt += """
## Recent Memories (Past Context)
"""
    if memories:
        for mem in memories:
            prompt += f"- [{mem['timestamp']}] {mem['action_type']}: {mem['detail']}\n"
    else:
        prompt += "No memories yet.\n"
    
    # Add instruction for JSON output
    prompt += """
## Your Action

Based on your persona, current location, nearby agents, and memories, decide what to do next.

You MUST respond with a valid JSON object containing exactly these keys:
- "action": One of "move", "talk", or "wait"
- "dialogue": (Only required if action is "talk") The words you will speak

If action is "move", specify direction in a "direction" key (one of: "up", "down", "left", "right").
If action is "wait", do not include a "dialogue" key.

Example responses:
{"action": "wait"}
{"action": "move", "direction": "up"}
{"action": "talk", "dialogue": "Greetings, friend!"}

Output ONLY the JSON, nothing else.
"""
    
    return prompt


if __name__ == "__main__":
    # Test the persona prompt generator
    print("=== Testing Persona Prompt Generator ===\n")
    
    # Test with agent 1 (The Mayor)
    print("Generating prompt for Agent 1 (The Mayor):")
    print("-" * 50)
    prompt = generate_agent_prompt(1)
    print(prompt)
    print("\n" + "=" * 50 + "\n")
    
    # Test with agent 2 (The Merchant)
    print("Generating prompt for Agent 2 (The Merchant):")
    print("-" * 50)
    prompt = generate_agent_prompt(2)
    print(prompt)
    print("\n" + "=" * 50 + "\n")
    
    # Test with agent 3 (The Hermit)
    print("Generating prompt for Agent 3 (The Hermit):")
    print("-" * 50)
    prompt = generate_agent_prompt(3)
    print(prompt)
    print("\n" + "=" * 50 + "\n")
    
    # Test error handling
    print("Testing error handling (non-existent agent):")
    try:
        prompt = generate_agent_prompt(999)
    except ValueError as e:
        print(f"  Caught expected error: {e}")
