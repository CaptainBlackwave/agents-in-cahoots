#!/usr/bin/env python3
"""
Streamlit Dashboard for Agents in Cahoots
Real-time visualization of multi-agent simulation.
"""

import streamlit as st
import sqlite3
import os
import time
import json
from datetime import datetime
from typing import Optional

DB_PATH = os.environ.get("DATABASE_URL", "game_state.db")


st.set_page_config(
    page_title="Agents in Cahoots",
    page_icon="🤖",
    layout="wide"
)


def get_db_connection():
    return sqlite3.connect(DB_PATH)


def get_agents():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, persona_description, current_x, current_y FROM agents")
    agents = []
    for row in cursor.fetchall():
        agents.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "x": row[3],
            "y": row[4]
        })
    conn.close()
    return agents


def get_locations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, name, description FROM locations")
    locations = {}
    for row in cursor.fetchall():
        locations[(row[0], row[1])] = {"name": row[2], "description": row[3]}
    conn.close()
    return locations


def get_recent_events(limit: int = 50):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, agent_id, action_type, detail 
        FROM event_logs 
        ORDER BY id DESC 
        LIMIT ?
    """, (limit,))
    events = []
    for row in cursor.fetchall():
        events.append({
            "id": row[0],
            "timestamp": row[1],
            "agent_id": row[2],
            "action_type": row[3],
            "detail": row[4]
        })
    conn.close()
    return events


def get_agent_name(agent_id: Optional[int]) -> str:
    if agent_id is None:
        return "SYSTEM"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM agents WHERE id = ?", (agent_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else f"Agent #{agent_id}"


def render_grid():
    """Render the 3x3 grid with agents."""
    agents = get_agents()
    locations = get_locations()
    
    st.subheader("🏰 World Map")
    
    cols = st.columns(3)
    
    for y in range(2, -1, -1):
        for x in range(3):
            location = locations.get((x, y), {"name": "Unknown", "description": ""})
            agents_here = [a for a in agents if a["x"] == x and a["y"] == y]
            
            with cols[x]:
                location_emoji = "🏠"
                if "Forest" in location["name"]:
                    location_emoji = "🌲"
                elif "River" in location["name"]:
                    location_emoji = "🌊"
                elif "Mountain" in location["name"]:
                    location_emoji = "⛰️"
                elif "Village" in location["name"]:
                    location_emoji = "🏘️"
                elif "Cave" in location["name"]:
                    location_emoji = "🕳️"
                elif "Field" in location["name"]:
                    location_emoji = "🌾"
                
                with st.container():
                    st.markdown(f"**{location_emoji} {location['name']}**")
                    if agents_here:
                        for agent in agents_here:
                            st.markdown(f"  🤖 {agent['name']}")
                    else:
                        st.markdown("  _Empty_")
                    st.markdown("---")


def render_agents():
    """Render agent information."""
    agents = get_agents()
    
    st.subheader("🤖 Agents")
    
    for agent in agents:
        with st.expander(f"🤖 {agent['name']}"):
            st.markdown(f"**Description:** {agent['description']}")
            st.markdown(f"**Position:** ({agent['x']}, {agent['y']})")


def render_events():
    """Render event log."""
    st.subheader("📜 Event Log")
    
    events = get_recent_events(30)
    
    for event in reversed(events):
        agent_name = get_agent_name(event["agent_id"])
        
        color = "white"
        if event["action_type"] == "MOVE":
            color = "cyan"
        elif event["action_type"] == "TALK":
            color = "yellow"
        elif event["action_type"] == "WAIT":
            color = "green"
        
        try:
            dt = datetime.fromisoformat(event["timestamp"])
            time_str = dt.strftime("%H:%M:%S")
        except:
            time_str = event["timestamp"][:8]
        
        st.markdown(f":{color}[{time_str}] **{event['action_type']}** - {agent_name}: {event['detail']}")


def render_controls():
    """Render control panel."""
    st.subheader("⚙️ Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ Run Tick"):
            st.info("Run tick functionality coming soon!")
    
    with col2:
        if st.button("⏹️ Stop"):
            st.info("Stop functionality coming soon!")
    
    with col3:
        if st.button("🔄 Reset"):
            st.info("Reset functionality coming soon!")
    
    st.markdown("### Settings")
    
    tick_delay = st.slider("Tick Delay (seconds)", 0.1, 5.0, 1.0)
    max_ticks = st.number_input("Max Ticks", 1, 100, 10)
    mock_mode = st.checkbox("Mock Mode", value=False)


def main():
    st.title("🤖 Agents in Cahoots")
    st.markdown("Real-time multi-agent simulation dashboard")
    
    if not os.path.exists(DB_PATH):
        st.error(f"Database not found at {DB_PATH}. Run setup_database.py first!")
        return
    
    render_grid()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        render_events()
    
    with col2:
        render_agents()
        render_controls()
    
    st.markdown("---")
    st.markdown("*Dashboard auto-refreshes every 5 seconds*")
    
    time.sleep(5)
    st.rerun()


if __name__ == "__main__":
    main()
