#!/usr/bin/env python3
"""
CLI Dashboard for Agents in Cahoots
Live-updating terminal that tails the event_logs table.
"""

import sqlite3
import os
import sys
import time
import argparse
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.db")

# ANSI colors for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Agent action colors
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Status colors
    RED = "\033[91m"
    ORANGE = "\033[38;5;208m"


def get_agent_name(cursor, agent_id):
    """Get agent name by ID."""
    if agent_id is None:
        return "SYSTEM"
    cursor.execute("SELECT name FROM agents WHERE id = ?", (agent_id,))
    result = cursor.fetchone()
    return result[0] if result else f"Agent #{agent_id}"


def get_location(cursor, x, y):
    """Get location name by coordinates."""
    cursor.execute("SELECT name FROM locations WHERE x = ? AND y = ?", (x, y))
    result = cursor.fetchone()
    return result[0] if result else f"({x}, {y})"


def format_event(cursor, row):
    """Format an event log row for display."""
    event_id, timestamp, agent_id, action_type, detail = row
    
    agent_name = get_agent_name(cursor, agent_id)
    
    # Parse timestamp
    try:
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime("%H:%M:%S")
    except:
        time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
    
    # Color by action type
    action_colors = {
        "MOVE": Colors.CYAN,
        "SPEAK": Colors.YELLOW,
        "TRADE": Colors.GREEN,
        "OBSERVE": Colors.BLUE,
        "MEET": Colors.MAGENTA,
        "SYSTEM": Colors.DIM + Colors.WHITE,
    }
    color = action_colors.get(action_type.upper(), Colors.WHITE)
    
    # Format detail - might contain location or message
    detail_formatted = detail if detail else ""
    
    # Build the output line
    line = f"{Colors.DIM}{time_str}{Colors.RESET} "
    line += f"{color}{action_type.upper()}{Colors.RESET} "
    
    if agent_id is not None:
        line += f"{Colors.BOLD}{agent_name}{Colors.RESET}"
        if detail_formatted:
            line += f": {detail_formatted}"
    else:
        line += f"{detail_formatted}"
    
    return line


def get_last_event_id(cursor):
    """Get the most recent event ID."""
    cursor.execute("SELECT MAX(id) FROM event_logs")
    result = cursor.fetchone()
    return result[0] if result[0] else 0


def show_header():
    """Print dashboard header."""
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{Colors.BOLD}{'═' * 60}")
    print(f"  🫘 Agents in Cahoots - Live Dashboard")
    print(f"{'═' * 60}{Colors.RESET}")
    print(f"{Colors.DIM}Press Ctrl+C to exit{Colors.RESET}\n")


def show_agents_summary(cursor):
    """Show current agent positions."""
    print(f"{Colors.BOLD}📍 Agent Locations:{Colors.RESET}")
    cursor.execute("SELECT id, name, current_x, current_y FROM agents")
    for row in cursor.fetchall():
        agent_id, name, x, y = row
        location_name = get_location(cursor, x, y)
        print(f"   • {name}: at {location_name} ({x}, {y})")
    print()


def tail_events(cursor, poll_interval=1, max_display=50):
    """Continuously poll for new events."""
    last_id = get_last_event_id(cursor)
    display_count = 0
    
    while True:
        try:
            # Check for new events
            cursor.execute(
                "SELECT id, timestamp, agent_id, action_type, detail FROM event_logs WHERE id > ? ORDER BY id ASC",
                (last_id,)
            )
            new_events = cursor.fetchall()
            
            if new_events:
                for event in new_events:
                    print(format_event(cursor, event))
                    display_count += 1
                    last_id = event[0]
                
                # Show summary if we've displayed a lot
                if display_count > max_display:
                    display_count = 0
                    show_agents_summary(cursor)
            
            time.sleep(poll_interval)
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}👋 Dashboard stopped.{Colors.RESET}")
            break
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.RESET}")
            time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Live dashboard for Agents in Cahoots")
    parser.add_argument("--poll", "-p", type=float, default=1.0, 
                        help="Poll interval in seconds (default: 1)")
    parser.add_argument("--db", "-d", type=str, default=DB_PATH,
                        help=f"Path to database (default: {DB_PATH})")
    parser.add_argument("--once", "-o", action="store_true",
                        help="Show current events once and exit (no live tail)")
    args = parser.parse_args()
    
    db_path = args.db
    
    if not os.path.exists(db_path):
        print(f"{Colors.RED}Error: Database not found at {db_path}{Colors.RESET}")
        print("Run setup_database.py first to initialize the database.")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    show_header()
    
    if args.once:
        # Show all events once and exit
        print(f"{Colors.BOLD}📜 Event History:{Colors.RESET}\n")
        cursor.execute("SELECT id, timestamp, agent_id, action_type, detail FROM event_logs ORDER BY id")
        for row in cursor.fetchall():
            print(format_event(cursor, row))
        print(f"\n{Colors.DIM}Total events: {cursor.execute('SELECT COUNT(*) FROM event_logs').fetchone()[0]}{Colors.RESET}")
    else:
        # Live tail mode
        print(f"{Colors.BOLD}📜 Live Event Feed:{Colors.RESET} (polling every {args.poll}s)\n")
        show_agents_summary(cursor)
        print(f"{Colors.DIM}Waiting for events...{Colors.RESET}\n")
        
        tail_events(cursor, poll_interval=args.poll)
    
    conn.close()


if __name__ == "__main__":
    main()
