#!/usr/bin/env python3
"""
Format a game run's events.jsonl into a readable script format.
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def format_timestamp(ts_str):
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.strftime("%H:%M:%S")
    except:
        return ts_str


def format_event(event, game_state):
    """Format a single event into readable text."""
    event_type = event.get("event_type", "unknown")
    data = event.get("data", {})
    timestamp = format_timestamp(event.get("timestamp", ""))
    
    lines = []
    
    if event_type == "game_start":
        players = data.get("players", [])
        mafia = data.get("mafia", [])
        sheriff = data.get("sheriff")
        lines.append("=" * 80)
        lines.append("GAME START")
        lines.append("=" * 80)
        lines.append(f"Players: {', '.join(f'Player {p}' for p in players)}")
        lines.append(f"Mafia: {', '.join(f'Player {p}' for p in mafia)}")
        lines.append(f"Sheriff: Player {sheriff}")
        lines.append("")
        
    elif event_type == "phase_change":
        phase = data.get("phase", "").upper()
        day = data.get("day_number", 0)
        night = data.get("night_number", 0)
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"{phase} PHASE - Day {day}, Night {night}")
        lines.append("=" * 80)
        lines.append("")
        
    elif event_type == "announcement":
        message = data.get("message", "")
        lines.append(f"[{timestamp}] {message}")
        lines.append("")
        
    elif event_type == "speech":
        player = data.get("player_number", "?")
        speech = data.get("speech", "")
        day = data.get("day_number", "?")
        is_final = "Final Speech" in speech or "final words" in speech.lower()
        
        if is_final:
            lines.append("")
            lines.append("-" * 80)
            lines.append(f"PLAYER {player} (FINAL SPEECH):")
            lines.append("-" * 80)
        else:
            lines.append(f"PLAYER {player} (Day {day}):")
        lines.append(speech)
        lines.append("")
        
    elif event_type == "nomination":
        if data.get("success", False):
            nominator = data.get("nominator", "?")
            target = data.get("target", "?")
            lines.append(f"[{timestamp}] Player {nominator} nominates Player {target}")
            lines.append("")
            
    elif event_type == "voting_start":
        nominations = data.get("nominations", [])
        lines.append(f"[{timestamp}] VOTING PHASE - Nominated: {', '.join(f'Player {n}' for n in nominations)}")
        lines.append("")
        
    elif event_type == "vote":
        voter = data.get("voter", "?")
        target = data.get("target", "?")
        day = data.get("day_number", "?")
        lines.append(f"[{timestamp}] Player {voter} votes for Player {target}")
        
    elif event_type == "vote_results":
        vote_counts = data.get("vote_counts", {})
        lines.append("")
        lines.append("VOTE RESULTS:")
        for player, count in sorted(vote_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  Player {player}: {count} votes")
        lines.append("")
        
    elif event_type == "elimination":
        player_num = data.get("player_number", "?")
        voters = data.get("voters", [])
        day = data.get("day_number")
        night = data.get("night_number")
        reason = data.get("reason", "")
        
        lines.append("")
        lines.append("!" * 80)
        
        # Format the elimination message based on reason
        if reason == "night kill":
            if night is not None:
                lines.append(f"Player {player_num} was KILLED (Night {night})")
            else:
                lines.append(f"Player {player_num} was KILLED")
        else:
            if day is not None:
                lines.append(f"Player {player_num} was ELIMINATED (Day {day})")
            else:
                lines.append(f"Player {player_num} was ELIMINATED")
        
        if voters:
            lines.append(f"Voted by: {', '.join(f'Player {v}' for v in voters)}")
        lines.append("!" * 80)
        lines.append("")
        
    elif event_type == "night_kill":
        killed = data.get("killed", "?")
        night = data.get("night_number", "?")
        lines.append("")
        lines.append("!" * 80)
        lines.append(f"Player {killed} was KILLED (Night {night})")
        lines.append("!" * 80)
        lines.append("")
        
    elif event_type == "game_over":
        winner = data.get("winner", "?").upper()
        reason = data.get("reason", "")
        day = data.get("day_number", "?")
        night = data.get("night_number", "?")
        lines.append("")
        lines.append("=" * 80)
        lines.append("GAME OVER")
        lines.append("=" * 80)
        lines.append(f"Winner: {winner} TEAM")
        lines.append(f"Ended: Day {day}, Night {night}")
        lines.append(f"Reason: {reason}")
        lines.append("=" * 80)
        lines.append("")
        
    return "\n".join(lines)


def format_run(run_dir, output_file):
    """Format a complete game run into a readable script."""
    events_file = Path(run_dir) / "events.jsonl"
    metadata_file = Path(run_dir) / "metadata.json"
    
    if not events_file.exists():
        print(f"Error: {events_file} not found")
        return False
    
    # Read metadata
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    
    # Read and format events
    output_lines = []
    
    # Header
    output_lines.append("=" * 80)
    output_lines.append("MAFIA GAME TRANSCRIPT")
    output_lines.append("=" * 80)
    output_lines.append(f"Run: {Path(run_dir).name}")
    if metadata:
        config = metadata.get("config", {})
        output_lines.append(f"Model: {config.get('llm_model', 'N/A')}")
        output_lines.append(f"Agent Type: {config.get('agent_type', 'N/A')}")
        output_lines.append(f"Seed: {config.get('random_seed', 'N/A')}")
    output_lines.append("")
    
    # Process events
    game_state = {
        "day": 0,
        "night": 0,
        "phase": "setup"
    }
    
    with open(events_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                formatted = format_event(event, game_state)
                if formatted:
                    output_lines.append(formatted)
                    
                # Update game state
                if event.get("event_type") == "phase_change":
                    data = event.get("data", {})
                    game_state["phase"] = data.get("phase", game_state["phase"])
                    game_state["day"] = data.get("day_number", game_state["day"])
                    game_state["night"] = data.get("night_number", game_state["night"])
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line: {e}")
                continue
    
    # Write output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines))
    
    print(f"Formatted script saved to: {output_path}")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: format_run_script.py <run_directory> [output_file]")
        print("Example: format_run_script.py runs/run_20260111_024040 scripts/run_20260111_024040.txt")
        sys.exit(1)
    
    run_dir = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        run_name = Path(run_dir).name
        output_file = f"scripts/{run_name}.txt"
    
    format_run(run_dir, output_file)


if __name__ == "__main__":
    main()

