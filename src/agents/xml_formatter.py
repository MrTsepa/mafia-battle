"""
XML formatter for game history.
Formats game events as structured XML for LLM prompts.
"""

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .base_agent import AgentContext


def format_game_history_xml(context: 'AgentContext', include_current_day: bool = True) -> str:
    """
    Format all game events (speeches, nominations, votes, eliminations, night kills) 
    as structured XML, similar to how events are stored in metadata.
    
    Only includes publicly available information (speeches, nominations, votes, eliminations, night kills).
    Events are ordered chronologically: Day 1, Night 1, Day 2, Night 2, etc.
    
    Args:
        context: Agent context containing game state and public history
        include_current_day: Whether to include events from the current day
        
    Returns:
        XML string with structured game history (max 120 chars per line)
    """
    current_day = context.game_state.day_number
    root = ET.Element("game_history")
    
    # Organize events by day/night
    day_events = {}  # {day_num: [events]}
    night_events = {}  # {night_num: [events]}
    
    # Track which players were eliminated via night kills to avoid duplicates
    night_killed_players = set()
    for night, killed_player in sorted(context.game_state.night_kills.items()):
        if killed_player:
            night_killed_players.add(killed_player)
    
    # Helper function to reconstruct speaking order for a given day
    def get_speaking_order_for_day(day_num: int, game_state, public_history_list) -> List[int]:
        """Reconstruct the speaking order for a given day."""
        # Get alive players at the start of that day
        # We need to reconstruct who was alive - players eliminated on this day or later were alive
        alive_at_day_start = []
        for player in game_state.players:
            # Check if player was eliminated before this day
            eliminated_before = False
            for action in game_state.action_log:
                if action["type"] == "player_eliminated":
                    elim_player = action["data"]["player"]
                    elim_day = action["data"].get("day_number")
                    elim_night = action["data"].get("night_number")
                    if elim_player == player.player_number:
                        # If eliminated on a previous day, they weren't alive
                        if elim_day and elim_day < day_num:
                            eliminated_before = True
                            break
                        # If eliminated on a previous night (night X happens before day X+1)
                        # Night 1 happens before Day 2, so night_num < day_num means eliminated before
                        if elim_night and elim_night < day_num:
                            eliminated_before = True
                            break
            
            if not eliminated_before:
                alive_at_day_start.append(player.player_number)
        
        if not alive_at_day_start:
            return []
        
        # Sort by player number for consistent ordering
        alive_at_day_start.sort()
        
        # Determine starting player for this day
        if day_num == 1:
            # First day: start with player 1 (if alive), otherwise first alive
            if 1 in alive_at_day_start:
                start_index = alive_at_day_start.index(1)
            else:
                start_index = 0
        else:
            # Subsequent days: find who started previous day by checking first speech
            prev_day = day_num - 1
            prev_day_starter = None
            
            # Find who was first to speak on previous day
            for event in public_history_list:
                if event.get("type") == "speech" and event.get("day") == prev_day and not event.get("is_final"):
                    prev_day_starter = event.get("player")
                    break
            
            if prev_day_starter and prev_day_starter in alive_at_day_start:
                start_index = (alive_at_day_start.index(prev_day_starter) + 1) % len(alive_at_day_start)
            else:
                # Fallback: rotate from player 1
                if 1 in alive_at_day_start:
                    # Day 2 would start with next after 1, Day 3 with next after that, etc.
                    day_1_start = 1
                    day_1_index = alive_at_day_start.index(day_1_start)
                    start_index = (day_1_index + (day_num - 1)) % len(alive_at_day_start)
                else:
                    start_index = (day_num - 1) % len(alive_at_day_start)
        
        # Rotate list to start at start_index
        return alive_at_day_start[start_index:] + alive_at_day_start[:start_index]
    
    # Collect all speeches
    regular_speeches = []
    final_speeches = []
    speech_by_day = {}  # {day: [speech_event]}
    
    for event in context.public_history:
        if event.get("type") == "speech":
            day = event.get("day", current_day)
            if not include_current_day and day == current_day:
                continue
            player = event.get("player", "?")
            speech = event.get("speech", "")
            is_final = event.get("is_final", False)
            
            speech_event = {
                "type": "speech",
                "day": day,
                "player": player,
                "text": speech,
                "is_final": is_final,
                "speech_num": 0  # Will be set below
            }
            
            if is_final:
                final_speeches.append(speech_event)
            else:
                regular_speeches.append(speech_event)
                if day not in speech_by_day:
                    speech_by_day[day] = []
                speech_by_day[day].append(speech_event)
    
    # Reconstruct speaking order for each day and assign speech numbers
    for day, speeches in speech_by_day.items():
        speaking_order = get_speaking_order_for_day(day, context.game_state, context.public_history)
        
        # Create a map from player to their position in speaking order
        player_to_position = {player: pos for pos, player in enumerate(speaking_order)}
        
        # Assign speech numbers based on speaking order
        for speech_event in speeches:
            player = speech_event["player"]
            # Use speaking order position, or fallback to player number if not found
            if player in player_to_position:
                speech_event["speech_num"] = player_to_position[player]
            else:
                # Fallback: use player number (not ideal but better than 0)
                speech_event["speech_num"] = player
    
    # Add regular speeches to day events
    for speech in regular_speeches:
        day = speech["day"]
        if day not in day_events:
            day_events[day] = []
        day_events[day].append(speech)
    
    # Collect nominations
    for day, nominations in context.game_state.nominations.items():
        if not include_current_day and day == current_day:
            continue
        if day not in day_events:
            day_events[day] = []
        for nom in nominations:
            day_events[day].append({
                "type": "nomination",
                "day": day,
                "target": nom
            })
    
    # Collect votes
    for day, votes in context.game_state.votes.items():
        if not include_current_day and day == current_day:
            continue
        if day not in day_events:
            day_events[day] = []
        # Group votes by target
        vote_targets = {}
        for voter, target in votes.items():
            if target not in vote_targets:
                vote_targets[target] = []
            vote_targets[target].append(voter)
        
        for target, voters in vote_targets.items():
            day_events[day].append({
                "type": "vote",
                "day": day,
                "target": target,
                "voters": voters
            })
    
    # Collect eliminations (skip night kills - handled separately)
    for event_data in context.public_history:
        if event_data.get("type") == "elimination":
            player = event_data.get("player", "?")
            reason = event_data.get("reason", "unknown")
            day = event_data.get("day")
            night = event_data.get("night")
            voters = event_data.get("voters", [])
            
            # Skip if this is a night kill
            if reason == "night kill" or player in night_killed_players:
                continue
            
            if day:
                if day not in day_events:
                    day_events[day] = []
                day_events[day].append({
                    "type": "elimination",
                    "day": day,
                    "player": player,
                    "reason": reason,
                    "voters": voters
                })
    
    # Add final speeches after eliminations (they appear on the same day)
    for speech in final_speeches:
        day = speech["day"]
        if day not in day_events:
            day_events[day] = []
        day_events[day].append(speech)
    
    # Collect night kills
    for night, killed_player in sorted(context.game_state.night_kills.items()):
        if killed_player:
            if night not in night_events:
                night_events[night] = []
            night_events[night].append({
                "type": "night_kill",
                "night": night,
                "target": killed_player
            })
    
    # Sort events within each day/night by type order
    # Order: speeches (0), nominations (1), votes (2), eliminations (3), final speeches (4)
    def get_sort_key(event):
        event_type = event.get("type", "")
        if event_type == "speech":
            if event.get("is_final", False):
                return (4, event.get("speech_num", 0), event.get("player", 0))
            else:
                return (0, event.get("speech_num", 0), event.get("player", 0))
        elif event_type == "nomination":
            return (1, 0, event.get("target", 0))
        elif event_type == "vote":
            return (2, 0, event.get("target", 0))
        elif event_type == "elimination":
            return (3, 0, event.get("player", 0))
        elif event_type == "night_kill":
            return (0, 0, event.get("target", 0))
        else:
            return (99, 0, 0)
    
    # Build XML structure in chronological order
    # Interleave days and nights: Day 1, Night 1, Day 2, Night 2, etc.
    all_periods = []
    
    # Add all days and nights to a unified list
    for day in sorted(day_events.keys()):
        all_periods.append(("day", day))
    for night in sorted(night_events.keys()):
        all_periods.append(("night", night))
    
    # Sort chronologically: Day 1, Night 1, Day 2, Night 2, etc.
    # Days come before nights of the same number, then next day/night pair
    def period_sort_key(period):
        period_type, number = period
        # Days get even sort keys, nights get odd (so Day 1=2, Night 1=3, Day 2=4, Night 2=5)
        if period_type == "day":
            return number * 2
        else:  # night
            return number * 2 + 1
    
    all_periods.sort(key=period_sort_key)
    
    # Process periods in chronological order
    for period_type, number in all_periods:
        if period_type == "day":
            day_elem = ET.SubElement(root, "day", number=str(number))
            events = sorted(day_events[number], key=get_sort_key)
            
            for event in events:
                if event["type"] == "speech":
                    speech_elem = ET.SubElement(day_elem, "speech", player=str(event["player"]))
                    if event.get("is_final", False):
                        speech_elem.set("type", "final")
                    speech_elem.text = event["text"]
                
                elif event["type"] == "nomination":
                    nom_elem = ET.SubElement(day_elem, "nomination", target=str(event["target"]))
                
                elif event["type"] == "vote":
                    votes_elem = ET.SubElement(day_elem, "votes", target=str(event["target"]))
                    for voter in event["voters"]:
                        vote_elem = ET.SubElement(votes_elem, "vote", voter=str(voter))
                
                elif event["type"] == "elimination":
                    elim_elem = ET.SubElement(day_elem, "elimination", player=str(event["player"]))
                    if event.get("reason"):
                        elim_elem.set("reason", str(event["reason"]))
                    if event.get("voters"):
                        elim_elem.set("voters", ",".join([str(v) for v in event["voters"]]))
        
        elif period_type == "night":
            night_elem = ET.SubElement(root, "night", number=str(number))
            events = sorted(night_events[number], key=get_sort_key)
            
            for event in events:
                if event["type"] == "night_kill":
                    kill_elem = ET.SubElement(night_elem, "kill", target=str(event["target"]))
    
    # Convert to pretty XML string with line wrapping at 120 characters
    def format_xml_element(elem, indent_level=0, max_line_length=120):
        """Format XML element with proper indentation and line wrapping."""
        indent = "  " * indent_level
        result = []
        
        # Build opening tag
        tag_name = elem.tag
        attrs = []
        for key, value in elem.attrib.items():
            attrs.append(f'{key}="{value}"')
        
        if attrs:
            opening_tag = f"{indent}<{tag_name} {' '.join(attrs)}>"
        else:
            opening_tag = f"{indent}<{tag_name}>"
        
        # Check if element has text or children
        text = elem.text.strip() if elem.text and elem.text.strip() else None
        children = list(elem)
        
        if not text and not children:
            # Self-closing tag
            if attrs:
                result.append(f"{indent}<{tag_name} {' '.join(attrs)}/>")
            else:
                result.append(f"{indent}<{tag_name}/>")
            return result
        
        # Handle text content with wrapping
        if text:
            # Calculate available width for text (accounting for closing tag)
            closing_tag_len = len(f"</{tag_name}>")
            available_width = max_line_length - len(opening_tag) - closing_tag_len
            
            if len(text) <= available_width and not children:
                # Text fits on one line
                result.append(f"{opening_tag}{text}</{tag_name}>")
            else:
                # Text needs wrapping or has children
                result.append(opening_tag)
                # Wrap text content
                text_indent = "  " * (indent_level + 1)
                words = text.split()
                current_line = text_indent
                
                for word in words:
                    test_line = current_line + (" " if current_line != text_indent else "") + word
                    if len(test_line) <= max_line_length - 20:  # Leave some margin
                        current_line = test_line
                    else:
                        if current_line != text_indent:
                            result.append(current_line)
                        current_line = text_indent + word
                
                if current_line != text_indent:
                    result.append(current_line)
                
                # Add children if any
                if children:
                    for child in children:
                        result.extend(format_xml_element(child, indent_level + 1, max_line_length))
                
                result.append(f"{indent}</{tag_name}>")
        else:
            # No text, just children
            result.append(opening_tag)
            for child in children:
                result.extend(format_xml_element(child, indent_level + 1, max_line_length))
            result.append(f"{indent}</{tag_name}>")
        
        return result
    
    # Format the root element
    lines = format_xml_element(root, indent_level=0, max_line_length=120)
    return '\n'.join(lines)

