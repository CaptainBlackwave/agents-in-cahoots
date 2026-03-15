#!/usr/bin/env python3
"""
Game Loop Engine for Agents in Cahoots
Runs the simulation tick-by-tick, querying LLMs for agent actions.
"""

import sqlite3
import os
import sys
import json
import time
import subprocess
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Add script directory to path for local imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Configuration
DB_PATH = os.path.join(SCRIPT_DIR, "game_state.db")

# LLM Configuration (defaults, can be overridden via environment)
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
LLM_API_KEY = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "200"))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.7"))

# Simulation configuration
DEFAULT_TICKS = int(os.environ.get("SIMULATION_TICKS", "5"))
TICK_DELAY = float(os.environ.get("TICK_DELAY", "1.0"))  # seconds between ticks


def get_db_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


def get_all_agents():
    """Retrieve all agents from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, persona_description, current_x, current_y FROM agents")
    agents = []
    for row in cursor.fetchall():
        agents.append({
            "id": row[0],
            "name": row[1],
            "persona_description": row[2],
            "x": row[3],
            "y": row[4]
        })
    conn.close()
    return agents


def get_location_name(x, y):
    """Get location name by coordinates."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM locations WHERE x = ? AND y = ?", (x, y))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Unknown"


def store_memory(agent_id, action_type, detail):
    """
    Store an event as a memory in the event_logs table.
    
    Args:
        agent_id: The ID of the agent (or None for system events)
        action_type: Type of action (MOVE, TALK, WAIT, SYSTEM)
        detail: Description of what happened
    
    Returns:
        int: The ID of the inserted event log
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO event_logs (timestamp, agent_id, action_type, detail) VALUES (?, ?, ?, ?)",
        (timestamp, agent_id, action_type, detail)
    )
    
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return event_id


def call_llm(prompt):
    """
    Send a prompt to the LLM API and get the response.
    
    Args:
        prompt: The prompt to send to the LLM
    
    Returns:
        str: The LLM's response text, or None on failure
    """
    global LLM_API_URL, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE
    
    # Check if API key is configured
    if not LLM_API_KEY:
        print("  ⚠️  No LLM_API_KEY configured. Set LLM_API_KEY environment variable.")
        print("  💡 Falling back to mock mode for testing.")
        return None
    
    # Prepare the request payload (OpenAI-compatible format)
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE
    }
    
    # Convert payload to JSON
    payload_bytes = json.dumps(payload).encode('utf-8')
    
    # Create the request
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    
    request = Request(LLM_API_URL, data=payload_bytes, headers=headers, method='POST')
    
    try:
        with urlopen(request, timeout=30) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            
            # Extract the message content (OpenAI format)
            if "choices" in response_data and len(response_data["choices"]) > 0:
                return response_data["choices"][0]["message"]["content"]
            else:
                print(f"  ⚠️  Unexpected API response format: {response_data}")
                return None
                
    except HTTPError as e:
        print(f"  ⚠️  HTTP Error {e.code}: {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            print(f"  📄 Error response: {error_body[:500]}")
        except:
            pass
        return None
    except URLError as e:
        print(f"  ⚠️  URL Error: {e.reason}")
        return None
    except Exception as e:
        print(f"  ⚠️  Error calling LLM: {e}")
        return None


def mock_llm_response(agent_name, location_name):
    """
    Generate a mock LLM response for testing without API access.
    
    Args:
        agent_name: Name of the agent
        location_name: Current location
    
    Returns:
        dict: A mock JSON response
    """
    import random
    
    actions = ["wait", "move", "talk"]
    directions = ["up", "down", "left", "right"]
    
    # Randomly choose an action
    action = random.choice(actions)
    
    if action == "wait":
        return {"action": "wait"}
    elif action == "move":
        return {"action": "move", "direction": random.choice(directions)}
    else:  # talk
        dialogues = [
            f"Greetings from {location_name}!",
            f"Hello! I am {agent_name}.",
            f"What a fine day at {location_name}!",
            f"Anyone else here?",
            f"I wonder what's happening..."
        ]
        return {"action": "talk", "dialogue": random.choice(dialogues)}


def parse_llm_response(response_text):
    """
    Parse the LLM response text as JSON.
    
    Handles common issues:
    - Extra text before/after JSON
    - Markdown code blocks
    - Invalid JSON attempts recovery
    
    Args:
        response_text: Raw text response from LLM
    
    Returns:
        dict: Parsed JSON object, or None on failure
    """
    if not response_text:
        return None
    
    # Try direct parsing first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    import re
    
    # Match ```json ... ``` or ``` ... ```
    json_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find any JSON object in the text
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Last resort: try to extract action and dialogue manually
    print(f"  ⚠️  Could not parse JSON from response: {response_text[:200]}")
    return None


def execute_agent_action(agent, parsed_response):
    """
    Execute the action specified in the parsed LLM response.
    
    Args:
        agent: Agent dictionary with id, name, x, y
        parsed_response: Parsed JSON response from LLM
    
    Returns:
        tuple: (success: bool, action_type: str, detail: str)
    """
    if not parsed_response:
        return (False, "ERROR", "Failed to parse LLM response")
    
    action = parsed_response.get("action", "").lower()
    
    if action == "move":
        # Import and use movement module
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from movement import move_agent
        
        direction = parsed_response.get("direction", "").lower()
        if not direction:
            return (False, "ERROR", "Move action requires a 'direction' field")
        
        result = move_agent(agent["id"], direction)
        
        if result["success"]:
            return (True, "MOVE", result["message"])
        else:
            # Log the failed move attempt but don't crash
            return (False, "MOVE_FAILED", result["message"])
    
    elif action == "talk":
        dialogue = parsed_response.get("dialogue", "")
        if not dialogue:
            return (False, "ERROR", "Talk action requires a 'dialogue' field")
        
        location_name = get_location_name(agent["x"], agent["y"])
        detail = f'{agent["name"]} said at {location_name}: "{dialogue}"'
        
        # Store the dialogue as memory
        store_memory(agent["id"], "TALK", detail)
        
        return (True, "TALK", detail)
    
    elif action == "wait":
        location_name = get_location_name(agent["x"], agent["y"])
        detail = f'{agent["name"]} waited at {location_name}'
        
        # Store the wait action as memory
        store_memory(agent["id"], "WAIT", detail)
        
        return (True, "WAIT", detail)
    
    else:
        return (False, "ERROR", f"Unknown action: {action}")


def run_tick(tick_number):
    """
    Run a single tick of the simulation.
    
    Args:
        tick_number: The current tick number
    
    Returns:
        int: Number of successful agent actions
    """
    print(f"\n{'='*60}")
    print(f"🔄 TICK {tick_number}")
    print(f"{'='*60}")
    
    agents = get_all_agents()
    successful_actions = 0
    
    for agent in agents:
        print(f"\n👤 Agent: {agent['name']} (ID: {agent['id']})")
        print(f"   Location: ({agent['x']}, {agent['y']}) - {get_location_name(agent['x'], agent['y'])}")
        
        # Generate the prompt for this agent
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from persona_prompt import generate_agent_prompt
        
        try:
            prompt = generate_agent_prompt(agent["id"])
        except ValueError as e:
            print(f"   ❌ Error generating prompt: {e}")
            continue
        
        # Call the LLM
        print(f"   📡 Calling LLM...")
        response_text = call_llm(prompt)
        
        # If LLM call failed (no API key or error), use mock mode
        if response_text is None:
            print(f"   🎭 Using mock response (no API configured)")
            location_name = get_location_name(agent["x"], agent["y"])
            parsed_response = mock_llm_response(agent["name"], location_name)
        else:
            print(f"   📥 Response: {response_text[:100]}...")
            # Parse the JSON response
            parsed_response = parse_llm_response(response_text)
        
        if parsed_response is None:
            print(f"   ❌ Failed to parse LLM response as JSON")
            # Store error as memory but don't crash
            store_memory(agent["id"], "ERROR", f"Failed to parse LLM response")
            continue
        
        print(f"   ✅ Parsed action: {parsed_response}")
        
        # Execute the action
        success, action_type, detail = execute_agent_action(agent, parsed_response)
        
        if success:
            print(f"   ✅ {action_type}: {detail}")
            successful_actions += 1
        else:
            print(f"   ⚠️  {action_type}: {detail}")
    
    return successful_actions


def run_simulation(num_ticks=None, verbose=True):
    """
    Run the complete simulation for a specified number of ticks.
    
    Args:
        num_ticks: Number of ticks to run (default from config)
        verbose: Whether to print detailed output
    
    Returns:
        dict: Summary of the simulation run
    """
    if num_ticks is None:
        num_ticks = DEFAULT_TICKS
    
    if not verbose:
        # Suppress output
        import io
        sys.stdout = io.StringIO()
    
    print(f"\n🚀 Starting Simulation: {num_ticks} ticks")
    print(f"   LLM API: {LLM_API_URL}")
    print(f"   Model: {LLM_MODEL}")
    print(f"   Database: {DB_PATH}")
    
    # Check database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("   Run setup_database.py first!")
        return {"success": False, "error": "Database not found"}
    
    total_successful = 0
    
    for tick in range(1, num_ticks + 1):
        successful = run_tick(tick)
        total_successful += successful
        
        if tick < num_ticks:
            print(f"\n⏳ Waiting {TICK_DELAY}s before next tick...")
            time.sleep(TICK_DELAY)
    
    if not verbose:
        # Restore stdout
        sys.stdout = sys.__stdout__
    
    print(f"\n{'='*60}")
    print(f"🏁 Simulation Complete")
    print(f"{'='*60}")
    print(f"   Total ticks: {num_ticks}")
    print(f"   Successful actions: {total_successful}")
    
    return {
        "success": True,
        "ticks": num_ticks,
        "successful_actions": total_successful
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run the Agents in Cahoots simulation")
    parser.add_argument("-n", "--ticks", type=int, default=DEFAULT_TICKS,
                        help=f"Number of ticks to run (default: {DEFAULT_TICKS})")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Quiet mode (less output)")
    parser.add_argument("--no-delay", action="store_true",
                        help="No delay between ticks")
    
    args = parser.parse_args()
    
    if args.no_delay:
        TICK_DELAY = 0
    
    result = run_simulation(args.ticks, verbose=not args.quiet)
    
    if result.get("success"):
        sys.exit(0)
    else:
        sys.exit(1)
