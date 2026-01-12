"""
Strategic LLM Agent implementation using OpenAI API.
Implements strategic decision-making based on game analysis learnings.
"""

import os
import re
import time
from typing import Dict, Any, List, Optional, TYPE_CHECKING

try:
    from openai import AsyncOpenAI
    from openai import OpenAI
except ImportError:
    AsyncOpenAI = None
    OpenAI = None

from .base_agent import BaseAgent, AgentContext
from .exceptions import LLMEmptyResponseError
from .xml_formatter import format_game_history_xml
from ..core import Player, GamePhase, RoleType
from ..config.game_config import GameConfig, default_config

if TYPE_CHECKING:
    from ..web.event_emitter import EventEmitter

# Constants
SYSTEM_MESSAGE = "You are a strategic player in a Mafia game. Make decisions based on the information provided."
SPEECH_ENDINGS = ("PASS", "THANK YOU")
NIGHT_EVENT_OFFSET = 1000  # Used to sort night events after day events


class SimpleLLMAgent(BaseAgent):
    """
    Strategic LLM agent implementation using OpenAI Responses API.
    
    Uses the Responses API to enable reasoning summaries that provide insight into
    the model's decision-making process. Reasoning summaries are extracted and displayed
    in the web UI.
    
    Key improvements over random strategy:
    - Sheriff checks suspicious players strategically
    - Civilians coordinate voting based on patterns
    - Mafia targets threats (sheriff, active players)
    - Uses game history and voting patterns effectively
    - Early game awareness (games end in 2-4 rounds)
    """
    
    def __init__(self, player: Player, config: GameConfig = default_config, event_emitter: Optional['EventEmitter'] = None):
        super().__init__(player, config)
        self.model = config.llm_model or "gpt-5-mini"
        self.temperature = config.llm_temperature
        self.reasoning_effort = config.reasoning_effort
        self.event_emitter = event_emitter
        
        # Initialize OpenAI client if available
        if OpenAI is None:
            raise ImportError("OpenAI package not installed. Install with: uv sync")
        
        # Note: OPENAI_API_KEY is loaded from .env file via dotenv (load_dotenv() is called in main.py)
        # If accessing API keys in other modules, ensure load_dotenv() is called first
        api_key = os.getenv("OPENAI_API_KEY")
        # Allow initialization without API key in test environments (tests use mocking)
        if not api_key:
            # Check if we're in a test environment
            import sys
            is_test_env = "pytest" in sys.modules or "unittest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
            if not is_test_env:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            # In test environment, set clients to None (methods will be mocked anyway)
            self.client = None
            self.async_client = None
        else:
            self.client = OpenAI(api_key=api_key)
            self.async_client = AsyncOpenAI(api_key=api_key) if AsyncOpenAI else None
        
        # Track strategic information
        self.checked_players: set[int] = set()  # For sheriff/don
        
        # Store last reasoning from LLM calls (for event emission)
        self.last_reasoning: Optional[str] = None
    
    def _build_api_params(self, prompt: str, max_tokens: Optional[int], temperature: Optional[float]) -> Dict[str, Any]:
        """
        Build API parameters for OpenAI Responses API calls.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response (None for unlimited)
            temperature: Temperature for generation
            
        Returns:
            Dictionary of API parameters
        """
        # Map reasoning_effort from config to reasoning parameters
        # reasoning_effort: "low" -> effort="low", summary="concise"
        #                  "medium" -> effort="medium", summary="auto"  
        #                  "high" -> effort="high", summary="detailed"
        # Note: For gpt-5.2, try "detailed" for high effort to get reasoning text
        reasoning_effort_value = "medium"  # Default effort
        reasoning_summary = "auto"  # Default to "auto" for summary
        
        if self.reasoning_effort:
            effort_lower = self.reasoning_effort.lower()
            if effort_lower == "low":
                reasoning_effort_value = "low"
                reasoning_summary = "concise"  # Use "concise" for low effort
            elif effort_lower == "medium":
                reasoning_effort_value = "medium"
                reasoning_summary = "auto"
            elif effort_lower == "high":
                reasoning_effort_value = "high"
                # For high effort, try "detailed" - this might be needed for gpt-5.2 to return reasoning
                reasoning_summary = "detailed"
        
        # Use Responses API (gpt-5.2-pro requires Responses API, not Chat Completions)
        # We'll request JSON in the prompt and parse it manually
        api_params: Dict[str, Any] = {
            "model": self.model,
            "input": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": prompt}
            ]
        }
        
        # Add reasoning effort for gpt-5 models
        if "gpt-5" in self.model:
            api_params["reasoning"] = {
                "effort": reasoning_effort_value,
                "summary": reasoning_summary
            }
        
        selected_temperature = temperature if temperature is not None else self.temperature
        if selected_temperature is not None:
            api_params["temperature"] = selected_temperature
        
        # Responses API uses max_output_tokens
        if max_tokens is not None:
            api_params["max_output_tokens"] = max_tokens
        
        # gpt-5 models only support default temperature (1), don't set custom temperature
        if "gpt-5" in self.model and "temperature" in api_params:
            del api_params["temperature"]
        
        return api_params
    
    def _process_llm_response(self, response: Any, max_tokens: Optional[int], latency_ms: float) -> str:
        """
        Process Responses API response and extract content and reasoning from structured JSON output.
        The model is instructed to return JSON with "response" and "reasoning" fields.
        Stores reasoning in self.last_reasoning for later use.
        
        Args:
            response: OpenAI Responses API response object
            max_tokens: Maximum tokens requested
            latency_ms: Request latency in milliseconds
            
        Returns:
            Extracted content string (from structured output's "response" field)
            
        Raises:
            LLMEmptyResponseError: If response is empty or invalid
        """
        import json
        import re
        
        # Responses API structure: response.output[0] contains the output item
        if not hasattr(response, 'output') or not response.output or len(response.output) == 0:
            raise LLMEmptyResponseError(
                self.player.player_number,
                "llm_api_call",
                f"LLM API returned invalid response structure for Player {self.player.player_number}"
            )
        
        output_item = response.output[0]
        
        # Extract structured output (JSON) from content
        structured_output = None
        content = None
        reasoning = None
        
        # Try to get structured output from output_item.content
        raw_content = None
        if hasattr(output_item, 'content') and output_item.content is not None:
            if isinstance(output_item.content, str):
                raw_content = output_item.content
            elif hasattr(output_item.content, '__str__'):
                raw_content = str(output_item.content)
        
        # Check if there's a text attribute on the output_item
        if not raw_content and hasattr(output_item, 'text') and output_item.text:
            if isinstance(output_item.text, str):
                raw_content = output_item.text
        
        # Try to extract JSON from the raw content
        if raw_content:
            # First, try to parse the entire content as JSON
            try:
                structured_output = json.loads(raw_content)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from markdown code blocks or find JSON object
                # Look for JSON object pattern: { ... }
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_content, re.DOTALL)
                if json_match:
                    try:
                        structured_output = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        pass
                
                # If still no JSON, treat as plain text
                if not structured_output:
                    content = raw_content
        
        # Extract from structured output
        if structured_output:
            if isinstance(structured_output, dict):
                content = structured_output.get("response", "")
                reasoning = structured_output.get("reasoning", "")
            else:
                # If structured_output is not a dict, try to extract content
                content = str(structured_output)
        
        # Fallback: check response-level text fields if we don't have content yet
        if (not content or content.strip() == "") and hasattr(response, 'output_text'):
            output_text = response.output_text
            if isinstance(output_text, str):
                try:
                    structured_output = json.loads(output_text)
                    if isinstance(structured_output, dict):
                        content = structured_output.get("response", "")
                        reasoning = structured_output.get("reasoning", "")
                    else:
                        content = output_text
                except json.JSONDecodeError:
                    content = output_text
            elif hasattr(output_text, 'text'):
                content = output_text.text
        
        # Last resort: try to get any string representation
        if (not content or content.strip() == "") and hasattr(output_item, '__str__'):
            content_str = str(output_item)
            # Only use if it looks like actual content (not just object representation)
            if content_str and not content_str.startswith('<') and len(content_str) > 10:
                content = content_str
        
        if content is None:
            content = ""
        content = content.strip()
        
        # Reasoning is extracted from structured output above
        # Normalize and store reasoning for later use in context_data
        if reasoning:
            if isinstance(reasoning, str):
                self.last_reasoning = reasoning.strip()
            else:
                # Try to convert to string
                self.last_reasoning = str(reasoning).strip()
        else:
            self.last_reasoning = None
        
        # Emit metadata (Responses API uses input_tokens/output_tokens)
        if self.event_emitter and hasattr(response, 'usage') and response.usage:
            usage = response.usage
            # Responses API uses input_tokens and output_tokens
            prompt_tokens = getattr(usage, 'input_tokens', None) or getattr(usage, 'prompt_tokens', 0) or 0
            completion_tokens = getattr(usage, 'output_tokens', None) or getattr(usage, 'completion_tokens', 0) or 0
            total_tokens = getattr(usage, 'total_tokens', 0) or 0
            
            # Extract reasoning tokens if available (for reasoning models like gpt-5.2)
            reasoning_tokens = getattr(usage, 'reasoning_tokens', None) or 0
            
            # Get reasoning effort level that was used in the API call
            reasoning_effort_used = None
            if "gpt-5" in self.model and self.reasoning_effort:
                reasoning_effort_used = self.reasoning_effort.lower()
            
            # If total_tokens is not available, try to calculate it
            if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
                total_tokens = prompt_tokens + completion_tokens
            
            self.event_emitter.emit_llm_metadata(
                self.player.player_number,
                "llm_api_call",
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                self.model,
                reasoning_tokens=reasoning_tokens,
                reasoning_effort=reasoning_effort_used
            )
        
        return content
    
    async def _call_llm_async(self, prompt: str, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        """
        Async version of _call_llm for parallel execution.
        """
        # If async_client is None (test environment), return empty string (methods will be mocked)
        if self.async_client is None:
            return ""
        
        try:
            api_params = self._build_api_params(prompt, max_tokens, temperature)
            
            # Track latency
            start_time = time.time()
            # Use Responses API (required for gpt-5.2-pro)
            response = await self.async_client.responses.create(**api_params)
            latency_ms = (time.time() - start_time) * 1000
            
            return self._process_llm_response(response, max_tokens, latency_ms)
        except LLMEmptyResponseError:
            # Re-raise LLM empty response errors
            raise
        except Exception as e:
            # Other API errors are also fatal
            raise LLMEmptyResponseError(
                self.player.player_number,
                "llm_api_call",
                f"LLM API call failed for Player {self.player.player_number}: {e}"
            )
    
    def _call_llm(self, prompt: str, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        """
        Call OpenAI Responses API with the given prompt.
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation (uses config default if None)
            
        Returns:
            LLM response text
        """
        # If client is None (test environment), return empty string (methods will be mocked)
        if self.client is None:
            return ""
        
        try:
            api_params = self._build_api_params(prompt, max_tokens, temperature)
            
            # Track latency
            start_time = time.time()
            # Use Responses API (required for gpt-5.2-pro)
            response = self.client.responses.create(**api_params)
            latency_ms = (time.time() - start_time) * 1000
            
            return self._process_llm_response(response, max_tokens, latency_ms)
        except LLMEmptyResponseError:
            # Re-raise LLM empty response errors
            raise
        except Exception as e:
            # Other API errors are also fatal
            raise LLMEmptyResponseError(
                self.player.player_number,
                "llm_api_call",
                f"LLM API call failed for Player {self.player.player_number}: {e}"
            )
    
    def _extract_player_number(self, text: str, context: AgentContext) -> Optional[int]:
        """
        Extract player number from LLM response.
        
        Args:
            text: LLM response text
            context: Current game context
            
        Returns:
            Player number or None if not found
        """
        # Try to find a number in the text
        numbers = re.findall(r'\b([1-9]|10)\b', text)
        if numbers:
            player_num = int(numbers[0])
            # Verify it's a valid alive player
            alive_numbers = {p.player_number for p in context.game_state.get_alive_players()}
            if player_num in alive_numbers:
                return player_num
        
        return None
    
    def _get_nominated_players(self, context: AgentContext) -> set[int]:
        """
        Get all players who have been nominated across all days.
        
        Args:
            context: Current game context
            
        Returns:
            Set of player numbers who have been nominated
        """
        nominated = set()
        for day_noms in context.game_state.nominations.values():
            nominated.update(day_noms)
        return nominated
    
    def _get_active_civilians(self, context: AgentContext) -> List[Player]:
        """
        Get civilian players who have been nominated (active players).
        
        Args:
            context: Current game context
            
        Returns:
            List of active civilian players
        """
        civilians = context.game_state.get_civilian_players()
        nominated = self._get_nominated_players(context)
        return [p for p in civilians if p.player_number in nominated]
    
    def _get_kill_decision_fallback(self, context: AgentContext, kill_claims: Dict[int, int]) -> Optional[int]:
        """
        Get fallback target for kill decision when LLM doesn't provide one.
        
        Args:
            context: Current game context
            kill_claims: Dictionary of kill claims from mafia team
            
        Returns:
            Player number to kill, or None if no valid target
        """
        if kill_claims:
            # Use first claim
            return list(kill_claims.values())[0]
        
        # Fallback: kill random civilian
        civilians = context.game_state.get_civilian_players()
        if civilians:
            return civilians[0].player_number
        
        return None
    
    def _get_kill_claim_fallback(self, context: AgentContext) -> Optional[int]:
        """
        Get fallback target for kill claim when LLM doesn't provide one.
        Prefers active (nominated) players.
        
        Args:
            context: Current game context
            
        Returns:
            Player number to target, or None if no valid target
        """
        civilians = context.game_state.get_civilian_players()
        if not civilians:
            return None
        
        # Prefer targeting players who have been nominated (active)
        active_civilians = self._get_active_civilians(context)
        if active_civilians:
            return active_civilians[0].player_number
        
        return civilians[0].player_number
    
    def _format_check_results(self, checks: Dict[int, Any], check_type: str) -> List[str]:
        """
        Format check results for prompt.
        
        Args:
            checks: Dictionary mapping night numbers to check results
            check_type: Type of check ("don" or "sheriff")
            
        Returns:
            List of formatted check result strings
        """
        formatted = []
        for night in sorted(checks.keys()):
            check_data = checks[night]
            if isinstance(check_data, dict):
                # New format: {"target": player_num, "result": "Sheriff"/"Not the Sheriff"/"Red"/"Black"}
                target = check_data.get("target", "?")
                result = check_data.get("result", "?")
                formatted.append(f"  Night {night}: Player {target} is {result}")
            else:
                # Old format: just the result string (backward compatibility)
                formatted.append(f"  Night {night}: {check_data}")
        return formatted
    
    def _normalize_speech_ending(self, speech: str) -> str:
        """
        Ensure speech ends with PASS or THANK YOU.
        
        Args:
            speech: Speech text
            
        Returns:
            Speech with proper ending
        """
        if not (speech.upper().endswith(SPEECH_ENDINGS[0]) or speech.upper().endswith(SPEECH_ENDINGS[1])):
            speech += " " + SPEECH_ENDINGS[0]
        return speech
    
    
    def _format_chronological_events(self, context: AgentContext, include_current_day: bool = True) -> List[str]:
        """
        Format all game events (speeches, nominations, votes, eliminations, night kills) 
        in chronological order with timestamps.
        
        Format: [Day X][Player Y][Timestamp] event text...
        
        Returns a list of formatted event strings.
        
        DEPRECATED: Use format_game_history_xml from xml_formatter module for structured XML format.
        """
        events = []
        current_day = context.game_state.day_number
        
        # Collect all speeches with timestamps
        # Separate regular speeches from final speeches
        regular_speeches = []
        final_speeches = []
        
        for event in context.public_history:
            if event.get("type") == "speech":
                day = event.get("day", current_day)
                if not include_current_day and day == current_day:
                    continue
                player = event.get("player", "?")
                timestamp = event.get("timestamp", f"Day {day}, Speech #?")
                speech = event.get("speech", "")
                is_final = event.get("is_final", False)
                
                # Extract speech number from timestamp for better sorting
                speech_num = 0
                if "Speech #" in timestamp:
                    try:
                        speech_num = int(timestamp.split("Speech #")[1])
                    except:
                        pass
                
                speech_event = {
                    "type": "speech",
                    "day": day,
                    "night": None,
                    "timestamp": timestamp,
                    "player": player,
                    "text": speech,
                    "is_final": is_final
                }
                
                if is_final:
                    # Final speeches should appear after eliminations on the same day
                    # Use a higher sort order (4) so they come after eliminations (3)
                    speech_event["sort_key"] = (day, 4, speech_num, player)
                    final_speeches.append(speech_event)
                else:
                    # Regular speeches come first, sorted by speech number
                    speech_event["sort_key"] = (day, 0, speech_num, player)
                    regular_speeches.append(speech_event)
        
        # Add regular speeches first
        events.extend(regular_speeches)
        
        # Collect nominations with timestamps (they happen after speeches on same day)
        for day, nominations in context.game_state.nominations.items():
            if not include_current_day and day == current_day:
                continue
            for idx, nom in enumerate(nominations):
                events.append({
                    "type": "nomination",
                    "day": day,
                    "night": None,
                    "timestamp": f"Day {day}",
                    "player": nom,
                    "text": f"Player {nom} was nominated",
                    "sort_key": (day, 1, idx, nom)  # Nominations after speeches
                })
        
        # Collect votes with timestamps (they happen after nominations on same day)
        for day, votes in context.game_state.votes.items():
            if not include_current_day and day == current_day:
                continue
            vote_targets = {}
            for voter, target in votes.items():
                if target not in vote_targets:
                    vote_targets[target] = []
                vote_targets[target].append(voter)
            for idx, (target, voters) in enumerate(vote_targets.items()):
                voters_str = ", ".join([f"P{v}" for v in voters])
                events.append({
                    "type": "vote",
                    "day": day,
                    "night": None,
                    "timestamp": f"Day {day}",
                    "player": None,  # Votes don't have a single player
                    "voters": voters,
                    "target": target,
                    "text": f"→ Player {target}",  # Voters shown in brackets, not in text
                    "sort_key": (day, 2, idx, target)  # Votes after nominations
                })
        
        # Track which players were eliminated via night kills to avoid duplicates
        night_killed_players = set()
        for night, killed_player in sorted(context.game_state.night_kills.items()):
            if killed_player:
                night_killed_players.add(killed_player)
        
        # Collect eliminations with timestamps (skip night kills - they're handled separately)
        for event_data in context.public_history:
            if event_data.get("type") == "elimination":
                player = event_data.get("player", "?")
                reason = event_data.get("reason", "unknown")
                day = event_data.get("day")
                night = event_data.get("night")
                voters = event_data.get("voters", [])
                
                # Skip if this is a night kill (we'll add it separately from night_kills dict)
                if reason == "night kill" or player in night_killed_players:
                    continue
                
                if day:
                    timestamp = f"Day {day}"
                    sort_day = day
                    sort_order = 3  # Eliminations after votes
                else:
                    timestamp = "Unknown"
                    sort_day = 0
                    sort_order = 3
                events.append({
                    "type": "elimination",
                    "day": day,
                    "night": None,
                    "timestamp": timestamp,
                    "player": player,
                    "reason": reason,
                    "voters": voters,
                    "text": f"Player {player} eliminated ({reason})",
                    "sort_key": (sort_day, sort_order, 0, player)
                })
        
        # Collect night kills with timestamps (only from night_kills dict, not from eliminations)
        for night, killed_player in sorted(context.game_state.night_kills.items()):
            if killed_player:
                events.append({
                    "type": "night_kill",
                    "day": None,
                    "night": night,
                    "timestamp": f"Night {night}",
                    "player": killed_player,
                    "text": f"Player {killed_player} was killed",
                    "sort_key": (night + 1000, 0, 0, killed_player)  # Night events after day events
                })
        
        # Add final speeches after eliminations
        events.extend(final_speeches)
        
        # Sort all events chronologically
        events.sort(key=lambda x: x["sort_key"])
        
        # Format events in the new simplified format
        formatted = []
        for event in events:
            if event["type"] == "speech":
                # Format: [Day X, Speech #Y] speech text...
                # For final speeches, add a marker to make it clear
                timestamp = event.get("timestamp", f"Day {event['day']}, Speech #?")
                is_final = event.get("is_final", False)
                if is_final:
                    # Mark as final speech for clarity
                    formatted_line = f"[Day {event['day']}, Final Speech] {event['text']}"
                else:
                    formatted_line = f"[{timestamp}] {event['text']}"
                formatted.append(formatted_line)
            
            elif event["type"] == "nomination":
                # Format: [Day X] Player Y was nominated
                day = event.get("day", "?")
                formatted_line = f"[Day {day}] Player {event['player']} was nominated"
                formatted.append(formatted_line)
            
            elif event["type"] == "vote":
                # Format: [Day X] P1, P2 → Player Y
                day = event.get("day", "?")
                voters_str = ", ".join([f"P{v}" for v in event.get("voters", [])])
                target = event.get("target", "?")
                formatted_line = f"[Day {day}] {voters_str} → Player {target}"
                formatted.append(formatted_line)
            
            elif event["type"] == "elimination":
                # Format: [Day X] → Player Y was eliminated by [P1, P2, ...]
                day = event.get("day")
                night = event.get("night")
                player = event.get("player", "?")
                voters = event.get("voters", [])
                reason = event.get("reason", "unknown")
                
                if day:
                    prefix = f"[Day {day}]"
                elif night:
                    prefix = f"[Night {night}]"
                else:
                    prefix = "[Unknown]"
                
                if voters:
                    voters_str = ", ".join([f"P{v}" for v in voters])
                    formatted_line = f"{prefix} → Player {player} was eliminated by [{voters_str}]"
                else:
                    # For eliminations without voters, show reason
                    formatted_line = f"{prefix} → Player {player} was eliminated ({reason})"
                formatted.append(formatted_line)
            
            elif event["type"] == "night_kill":
                # Format: [Night X] Player Y was killed
                night = event.get("night", "?")
                player = event.get("player", "?")
                formatted_line = f"[Night {night}] Player {player} was killed"
                formatted.append(formatted_line)
        
        return formatted
    
    def build_strategic_prompt(self, context: AgentContext, action_type: str) -> str:
        """
        Build a strategic prompt based on game analysis learnings.
        
        Args:
            context: Current game context
            action_type: Type of action needed ("speech", "vote", "sheriff_check", "don_check", "kill_claim", "kill_decision")
            
        Returns:
            Formatted prompt string
        """
        role = self.player.role.role_type.value
        team = self.player.role.team.value
        
        prompt_parts = [
            f"You are Player {self.player.player_number}, a {role} on the {team} team.",
            "",
            "GAME RULES:",
            "- Red Team (Civilians) wins when all Mafia are eliminated",
            "- Black Team (Mafia) wins when numbers are equal or Mafia outnumber Civilians",
            "- Roles are NOT revealed when players are eliminated",
            "- Roles are NOT revealed at the end of the game",
            "- You can claim to have any role (both when it's true or false) - role claiming is allowed",
            "- Games typically end in 2-4 rounds, so early decisions are critical",
            "- Night kills account for ~50% of eliminations - they are very powerful",
            "- IMPORTANT: Once a nomination is made, it cannot be withdrawn",
            "",
        ]
        
        # Add role-specific strategic information
        if self.player.is_mafia:
            prompt_parts.extend([
                f"MAFIA TEAM: You know these players are mafia: {self.player.known_mafia}",
                "STRATEGY:",
                "- Target active players who might be sheriff or leading civilians",
                "- Coordinate with your team (you know who they are)",
                "- Avoid drawing attention to yourself",
                "",
            ])
            
            if self.player.role.role_type == RoleType.DON:
                prompt_parts.extend([
                    "DON ABILITIES:",
                    "- Check one player per night to see if they are the Sheriff",
                    "- Make final decision on who mafia kills each night",
                    "",
                    "DON STRATEGY:",
                    "- Prioritize checking players who seem to be leading or coordinating",
                    "- Check players who haven't been checked yet",
                    "",
                ])
        
        if self.player.role.role_type == RoleType.SHERIFF:
            prompt_parts.extend([
                "SHERIFF ABILITIES:",
                "- Check one player per night to see if they are Red (civilian) or Black (mafia)",
                "",
                "SHERIFF STRATEGY:",
                "- Check suspicious players (those who voted for eliminated civilians)",
                "- Check players who avoid nominations or seem to be hiding",
                "- Don't check randomly - use information from voting patterns",
                "",
            ])
        
        # Add game state
        alive_players = context.game_state.get_alive_players()
        mafia_count = len(context.game_state.get_mafia_players())
        civilian_count = len(context.game_state.get_civilian_players())
        
        prompt_parts.extend([
            f"CURRENT PHASE: {context.current_phase.value}",
            f"DAY: {context.game_state.day_number}, NIGHT: {context.game_state.night_number}",
            f"ALIVE: {len(alive_players)} players ({mafia_count} mafia, {civilian_count} civilians)",
            "",
        ])
        
        # Add game structure context based on day number
        day_num = context.game_state.day_number
        if day_num == 1:
            prompt_parts.extend([
                "GAME STRUCTURE - DAY 1:",
                "- This is the start of the game - we have no information yet",
                "- No eliminations have happened, no night actions have occurred",
                "- There's no reason to eliminate anybody yet - focus on gathering information",
                "- Use this day to observe behavior, make initial reads, and set up for future days",
                "",
            ])
        elif day_num == 2:
            prompt_parts.extend([
                "GAME STRUCTURE - DAY 2:",
                "- This is the day after the first night kill",
                "- Don and Sheriff now have their first check results (if they checked)",
                "- It makes sense to start suspecting someone and form teams",
                "- Use check results, voting patterns from Day 1, and behavior to identify mafia",
                "- This is when real investigation begins",
                "",
            ])
        elif day_num == 3:
            prompt_parts.extend([
                "GAME STRUCTURE - DAY 3:",
                "- We're now in the mid-game phase",
                "- Multiple checks have been performed, eliminations have happened",
                "- Voting patterns and team coordination should be clearer",
                "- Focus on players who have been avoiding suspicion or coordinating votes",
                "- Time is running out - make decisive moves",
                "",
            ])
        elif day_num >= 4:
            prompt_parts.extend([
                f"GAME STRUCTURE - DAY {day_num}:",
                "- We're in the late game - every decision is critical",
                "- Use all accumulated information: checks, voting patterns, eliminations",
                "- Focus on identifying remaining mafia quickly",
                "- The game could end at any moment - be decisive",
                "",
            ])
        
        # Add game history - structured XML format with publicly available information
        game_history_xml = format_game_history_xml(context, include_current_day=True)
        # Check if game history has actual content (not just empty root tags)
        has_content = game_history_xml.strip() and (
            '<day' in game_history_xml or '<night' in game_history_xml
        )
        if has_content:
            prompt_parts.append("GAME HISTORY (structured format):")
            # Split XML into lines and indent each line
            xml_lines = game_history_xml.strip().split('\n')
            for line in xml_lines:
                prompt_parts.append(line)
            prompt_parts.append("")
        else:
            prompt_parts.append("GAME HISTORY (structured format):")
            prompt_parts.append("Game history is empty - no events have occurred yet.")
            prompt_parts.append("")
        
        # Add alive players at the end
        prompt_parts.extend([
            "ALIVE PLAYERS:",
        ])
        for player in alive_players:
            prompt_parts.append(f"  Player {player.player_number}")
        prompt_parts.append("")
        
        # Add check results at the end
        if self.player.role.role_type == RoleType.SHERIFF and self.player.sheriff_checks:
            prompt_parts.append("YOUR CHECK RESULTS:")
            prompt_parts.extend(self._format_check_results(self.player.sheriff_checks, "sheriff"))
            prompt_parts.append("")
        
        if self.player.role.role_type == RoleType.DON and self.player.don_checks:
            prompt_parts.append("YOUR CHECK RESULTS:")
            prompt_parts.extend(self._format_check_results(self.player.don_checks, "don"))
            prompt_parts.append("")
        
        # Add phase-specific instructions
        if action_type == "final_speech":
            prompt_parts.extend([
                "FINAL SPEECH:",
                "- You have been eliminated from the game",
                "- This is your final opportunity to speak",
                "- Target length: 100-150 words",
                "- You can share your thoughts, accuse others, or reveal information",
                "- End your speech with 'PASS' or 'THANK YOU'",
                "",
                "Generate your final speech:",
            ])
        elif action_type == "speech":
            nominations = context.game_state.nominations.get(context.game_state.day_number, [])
            is_nominated = self.player.player_number in nominations
            
            prompt_parts.extend([
                "YOUR TURN TO SPEAK:",
                "- Target length: 100-150 words",
                "- You can nominate a player by saying 'I nominate player number X'",
                "- IMPORTANT: Once a nomination is made, it cannot be withdrawn - choose carefully",
                "- End your speech with 'PASS' or 'THANK YOU'",
                "- Analyze voting patterns and suspicious behavior",
                "- If you're sheriff, be careful not to reveal your role",
                "- Coordinate with your team if possible",
                f"- Current nominations: {nominations}",
            ])
            
            # Add critical strategic guidance
            if self.player.is_civilian:
                prompt_parts.append("- IMPORTANT: As a civilian, you know you are innocent - DO NOT nominate yourself")
                if is_nominated:
                    prompt_parts.extend([
                        "- CRITICAL: You are currently nominated! If only one player is nominated, you will be automatically eliminated",
                        "- You MUST nominate someone else (the most suspicious player) to create a voting choice",
                        "- This is your only chance to avoid automatic elimination - nominate the player you believe is mafia",
                    ])
                else:
                    prompt_parts.extend([
                        "- If you are nominated later, make sure to nominate someone else to avoid automatic elimination",
                        "- Focus on nominating players you believe are mafia based on voting patterns and behavior",
                    ])
            else:
                # Mafia can still nominate strategically, but shouldn't nominate themselves
                prompt_parts.append("- DO NOT nominate yourself")
            
            prompt_parts.extend([
                "",
                "Generate your strategic speech:",
            ])
        elif action_type == "vote":
            nominations = context.game_state.nominations.get(context.game_state.day_number, [])
            prompt_parts.extend([
                "VOTING PHASE:",
                f"Nominated players: {nominations}",
                "- Vote for the player you believe is most likely mafia",
                "- Consider voting patterns and suspicious behavior",
                "- IMPORTANT: If you are a civilian, you know you are innocent - DO NOT vote for yourself",
                "- If you are nominated, you must still vote for someone else (not yourself)",
                "- Return ONLY the player number (e.g., '5' or 'Player 5')",
            ])
        elif action_type == "sheriff_check":
            checked = list(self.checked_players)
            prompt_parts.extend([
                "SHERIFF CHECK:",
                "- Check one player (Red=civilian, Black=mafia)",
                f"- Already checked: {checked if checked else 'none'}",
                "- Return ONLY player number (e.g., '5')",
            ])
        elif action_type == "don_check":
            checked = list(self.checked_players)
            prompt_parts.extend([
                "DON CHECK:",
                "- Check one player (is they Sheriff?)",
                f"- Already checked: {checked if checked else 'none'}",
                "- Return ONLY player number (e.g., '5')",
            ])
        elif action_type == "kill_claim":
            prompt_parts.extend([
                "KILL CLAIM:",
                "- Suggest who to kill tonight",
                "- Target active players or potential sheriff",
                "- Return ONLY the player number (e.g., '5')",
            ])
        elif action_type == "kill_decision":
            kill_claims = context.private_info.get("mafia_kill_claims", {})
            if kill_claims:
                prompt_parts.extend([
                    "KILL DECISION:",
                    "- Team claims:",
                ])
                for player_num, target in kill_claims.items():
                    prompt_parts.append(f"  P{player_num} → P{target}")
                prompt_parts.extend([
                    "- Choose target to kill",
                    "- Return ONLY player number (e.g., '5')",
                ])
            else:
                prompt_parts.extend([
                    "KILL DECISION:",
                    "- No team claims",
                    "- Choose target to kill",
                    "- Return ONLY player number (e.g., '5')",
                ])
        
        # Add JSON format instruction at the end of all prompts
        prompt_parts.extend([
            "",
            "IMPORTANT: You must respond with valid JSON in the following format:",
            '{"reasoning": "explanation of your decision", "response": "your actual response here"}',
            "- The 'reasoning' field should contain an explanation of why you made this decision (target length: 50-150 words)",
            "- The 'response' field should contain your actual answer (speech, player number, etc.)",
            "- Both fields are required",
        ])
        
        return "\n".join(prompt_parts)
    
    def get_day_speech(self, context: AgentContext) -> str:
        """
        Generate strategic day speech using LLM.
        
        Args:
            context: Current game context
            
        Returns:
            The speech text
        """
        prompt = self.build_strategic_prompt(context, "speech")
        response = self._call_llm(prompt)
        return self._normalize_speech_ending(response)
    
    def get_final_speech(self, context: AgentContext) -> str:
        """
        Generate final speech when eliminated.
        
        Args:
            context: Current game context
            
        Returns:
            The final speech text
        """
        prompt = self.build_strategic_prompt(context, "final_speech")
        response = self._call_llm(prompt)
        return self._normalize_speech_ending(response)
    
    def _handle_sheriff_check(self, context: AgentContext) -> Dict[str, Any]:
        """
        Handle sheriff check action.
        
        Args:
            context: Current game context
            
        Returns:
            Dictionary containing action type and target
        """
        action = {}
        prompt = self.build_strategic_prompt(context, "sheriff_check")
        response = self._call_llm(prompt)
        
        target = self._extract_player_number(response, context)
        if target and target != self.player.player_number:
            action["type"] = "sheriff_check"
            action["target"] = target
            self.checked_players.add(target)
        else:
            # Fallback: check random available player
            alive_players = context.game_state.get_alive_players()
            available = [p.player_number for p in alive_players 
                        if p.player_number != self.player.player_number 
                        and p.player_number not in self.checked_players]
            
            if available:
                target = available[0]
                action["type"] = "sheriff_check"
                action["target"] = target
                self.checked_players.add(target)
        
        return action
    
    def _handle_mafia_kill_claim(self, context: AgentContext) -> Dict[str, Any]:
        """
        Handle mafia kill claim action.
        
        Args:
            context: Current game context
            
        Returns:
            Dictionary containing action type and target
        """
        action = {}
        prompt = self.build_strategic_prompt(context, "kill_claim")
        response = self._call_llm(prompt)
        
        target = self._extract_player_number(response, context)
        if not target:
            target = self._get_kill_claim_fallback(context)
        
        if target:
            action["type"] = "kill_claim"
            action["target"] = target
        
        return action
    
    def _handle_mafia_kill_decision(self, context: AgentContext, kill_claims: Dict[int, int]) -> Dict[str, Any]:
        """
        Handle mafia kill decision action (when Don is eliminated).
        
        Args:
            context: Current game context
            kill_claims: Dictionary of kill claims from mafia team
            
        Returns:
            Dictionary containing action type and target
        """
        action = {}
        prompt = self.build_strategic_prompt(context, "kill_decision")
        response = self._call_llm(prompt)
        
        target = self._extract_player_number(response, context)
        if not target:
            target = self._get_kill_decision_fallback(context, kill_claims)
        
        if target:
            action["kill_decision"] = target
            action["type"] = "kill_decision"
        
        return action
    
    def _handle_don_check(self, context: AgentContext) -> Dict[str, Any]:
        """
        Handle Don check action.
        
        Args:
            context: Current game context
            
        Returns:
            Dictionary containing action type and target
        """
        action = {}
        prompt = self.build_strategic_prompt(context, "don_check")
        response = self._call_llm(prompt)
        
        target = self._extract_player_number(response, context)
        if not target:
            # Fallback: check active players
            civilians = context.game_state.get_civilian_players()
            available = [p.player_number for p in civilians 
                        if p.player_number not in self.checked_players]
            
            if available:
                # Prefer checking nominated players (active)
                nominated = self._get_nominated_players(context)
                active_available = [p for p in available if p in nominated]
                if active_available:
                    target = active_available[0]
                else:
                    target = available[0]
        
        if target:
            action["type"] = "don_check"
            action["target"] = target
            self.checked_players.add(target)
        
        return action
    
    def _handle_don_kill_decision(self, context: AgentContext, kill_claims: Dict[int, int]) -> Dict[str, Any]:
        """
        Handle Don kill decision action.
        
        Args:
            context: Current game context
            kill_claims: Dictionary of kill claims from mafia team
            
        Returns:
            Dictionary containing action type and target
        """
        action = {}
        prompt = self.build_strategic_prompt(context, "kill_decision")
        response = self._call_llm(prompt)
        
        target = self._extract_player_number(response, context)
        if not target:
            target = self._get_kill_decision_fallback(context, kill_claims)
        
        if target:
            action["kill_decision"] = target
            action["type"] = "kill_decision"
        
        return action
    
    def _is_kill_decision_call(self, context: AgentContext) -> bool:
        """
        Determine if this is a kill decision call (Don or mafia when Don is eliminated).
        
        Args:
            context: Current game context
            
        Returns:
            True if this is a kill decision call, False otherwise
        """
        # Check explicit marker set by process_mafia_kill
        if context.private_info.get("_kill_decision_context", False):
            return True
        
        kill_claims = context.private_info.get("mafia_kill_claims", {})
        if not isinstance(kill_claims, dict) or not kill_claims:
            return False
        
        # If keys are player numbers (not night numbers), it's from process_mafia_kill
        alive_player_numbers = {p.player_number for p in context.game_state.get_alive_players()}
        keys = list(kill_claims.keys())
        all_keys_are_players = all(k in alive_player_numbers for k in keys)
        
        if not all_keys_are_players:
            return False
        
        # Check if keys look like night numbers (1, 2, 3, ...)
        keys_sorted = sorted(keys)
        looks_like_night_numbers = keys_sorted == list(range(1, len(keys) + 1))
        
        # If keys are player numbers but don't look like night numbers, it's a kill decision call
        return not looks_like_night_numbers
    
    def get_night_action(self, context: AgentContext) -> Dict[str, Any]:
        """
        Get strategic night action using LLM.
        
        Args:
            context: Current game context
            
        Returns:
            Dictionary containing action type and target
        """
        action = {}
        is_kill_decision_call = self._is_kill_decision_call(context)
        kill_claims = context.private_info.get("mafia_kill_claims", {})
        
        # Sheriff: Strategic check
        if self.player.role.role_type == RoleType.SHERIFF and not is_kill_decision_call:
            action.update(self._handle_sheriff_check(context))
        
        # Mafia: Kill claim or decision (but NOT Don - Don is handled separately below)
        if self.player.is_mafia and self.player.role.role_type != RoleType.DON:
            if is_kill_decision_call:
                # Check if Don is eliminated and we need to make decision
                don = next((p for p in context.game_state.get_mafia_players() 
                           if p.role.role_type == RoleType.DON and p.is_alive), None)
                
                if not don and "decide_kill" in context.available_actions:
                    action.update(self._handle_mafia_kill_decision(context, kill_claims))
            else:
                # Normal kill claim
                action.update(self._handle_mafia_kill_claim(context))
        
        # Don: Check and kill decision (handled separately to prioritize don_check over kill_claim)
        if self.player.role.role_type == RoleType.DON:
            # Priority 1: Don check (if this is a don check call, not kill decision)
            if (not is_kill_decision_call and 
                "don_check" in context.available_actions and
                context.game_state.night_number not in self.player.don_checks):
                action.update(self._handle_don_check(context))
            
            # Priority 2: Kill decision (when called with kill claims in context)
            if is_kill_decision_call and "decide_kill" in context.available_actions:
                action.update(self._handle_don_kill_decision(context, kill_claims))
            
            # Priority 3: Kill claim (only if we haven't already set don_check or kill_decision)
            # Don also makes a kill claim like other mafia during the kill claim phase
            if (not is_kill_decision_call and 
                action.get("type") not in ["don_check", "kill_decision"]):
                action.update(self._handle_mafia_kill_claim(context))
        
        return action
    
    def _process_vote_choice(self, response: str, context: AgentContext) -> int:
        """
        Process vote choice response and return valid target.
        
        Args:
            response: LLM response text
            context: Current game context
            
        Returns:
            Player number to vote against
        """
        nominations = context.game_state.nominations.get(context.game_state.day_number, [])
        if not nominations:
            # Fallback
            alive_players = context.game_state.get_alive_players()
            if alive_players:
                return alive_players[0].player_number
            return 1
        
        target = self._extract_player_number(response, context)
        
        # Prevent self-voting: if target is self, reject it
        if target == self.player.player_number:
            target = None
        
        # Verify target is in nominations
        if target and target in nominations:
            return target
        
        # Fallback to first nomination that isn't self
        valid_nominations = [n for n in nominations if n != self.player.player_number]
        if valid_nominations:
            return valid_nominations[0]
        
        # Last resort: if only self is nominated, this shouldn't happen but handle gracefully
        return nominations[0] if nominations else 1
    
    async def get_vote_choice_async(self, context: AgentContext) -> int:
        """
        Async version of get_vote_choice for parallel execution.
        
        Args:
            context: Current game context
            
        Returns:
            Player number to vote against
        """
        prompt = self.build_strategic_prompt(context, "vote")
        response = await self._call_llm_async(prompt)
        return self._process_vote_choice(response, context)
    
    def get_vote_choice(self, context: AgentContext) -> int:
        """
        Get strategic vote choice using LLM (synchronous version).
        
        Args:
            context: Current game context
            
        Returns:
            Player number to vote against
        """
        prompt = self.build_strategic_prompt(context, "vote")
        response = self._call_llm(prompt)
        return self._process_vote_choice(response, context)
