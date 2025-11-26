"""
Strategic LLM Agent implementation using OpenAI API.
Implements strategic decision-making based on game analysis learnings.
"""

import os
import re
import asyncio
import time
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from collections import defaultdict

try:
    from openai import AsyncOpenAI
    from openai import OpenAI
except ImportError:
    AsyncOpenAI = None
    OpenAI = None

from .base_agent import BaseAgent, AgentContext
from .exceptions import LLMEmptyResponseError
from ..core import Player, GamePhase, RoleType
from ..config.game_config import GameConfig, default_config

if TYPE_CHECKING:
    from ..web.event_emitter import EventEmitter


class SimpleLLMAgent(BaseAgent):
    """
    Strategic LLM agent implementation using OpenAI API.
    
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
        self.event_emitter = event_emitter
        
        # Initialize OpenAI client if available
        if OpenAI is None:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")
        
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
        self.suspicious_players: set[int] = set()  # Players to investigate
        self.trusted_players: set[int] = set()  # Players we trust
        self.voting_patterns: Dict[int, List[int]] = defaultdict(list)  # {player: [who_they_voted_for]}
        self.speech_analysis: Dict[int, List[str]] = defaultdict(list)  # {player: [speeches]}
    
    async def _call_llm_async(self, prompt: str, max_tokens: int = 200, temperature: Optional[float] = None) -> str:
        """
        Async version of _call_llm for parallel execution.
        """
        # If async_client is None (test environment), return empty string (methods will be mocked)
        if self.async_client is None:
            return ""
        
        try:
            # gpt-5-mini uses max_completion_tokens instead of max_tokens
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a strategic player in a Mafia game. Make decisions based on the information provided."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature or self.temperature
            }
            
            # Use max_completion_tokens for newer models (gpt-5-mini), max_tokens for older ones
            if "gpt-5" in self.model:
                api_params["max_completion_tokens"] = max_tokens
                # gpt-5-mini only supports default temperature (1), don't set custom temperature
                if "temperature" in api_params:
                    del api_params["temperature"]
            elif "gpt-4o" in self.model:
                api_params["max_completion_tokens"] = max_tokens
            else:
                api_params["max_tokens"] = max_tokens
            
            # Track latency
            start_time = time.time()
            response = await self.async_client.chat.completions.create(**api_params)
            latency_ms = (time.time() - start_time) * 1000
            
            content = response.choices[0].message.content
            if content is None:
                content = ""
            content = content.strip()
            
            # Emit metadata
            if self.event_emitter and response.usage:
                self.event_emitter.emit_llm_metadata(
                    self.player.player_number,
                    "llm_api_call",
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    response.usage.total_tokens,
                    latency_ms,
                    self.model
                )
            
            # Empty response is a fatal error
            if not content:
                raise LLMEmptyResponseError(
                    self.player.player_number,
                    "llm_api_call",
                    f"LLM API returned empty response for Player {self.player.player_number}. Model: {self.model}, Max tokens: {max_tokens}"
                )
            
            return content
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
    
    def _call_llm(self, prompt: str, max_tokens: int = 200, temperature: Optional[float] = None) -> str:
        """
        Call OpenAI API with the given prompt.
        
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
            # gpt-5-mini uses max_completion_tokens instead of max_tokens
            # Try max_completion_tokens first, fallback to max_tokens for older models
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a strategic player in a Mafia game. Make decisions based on the information provided."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature or self.temperature
            }
            
            # Use max_completion_tokens for newer models (gpt-5-mini), max_tokens for older ones
            if "gpt-5" in self.model:
                api_params["max_completion_tokens"] = max_tokens
                # gpt-5-mini only supports default temperature (1), don't set custom temperature
                if "temperature" in api_params:
                    del api_params["temperature"]
            elif "gpt-4o" in self.model:
                api_params["max_completion_tokens"] = max_tokens
            else:
                api_params["max_tokens"] = max_tokens
            
            # Track latency
            start_time = time.time()
            response = self.client.chat.completions.create(**api_params)
            latency_ms = (time.time() - start_time) * 1000
            
            content = response.choices[0].message.content
            if content is None:
                content = ""
            content = content.strip()
            
            # Emit metadata
            if self.event_emitter and response.usage:
                self.event_emitter.emit_llm_metadata(
                    self.player.player_number,
                    "llm_api_call",
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    response.usage.total_tokens,
                    latency_ms,
                    self.model
                )
            
            # Empty response is a fatal error
            if not content:
                raise LLMEmptyResponseError(
                    self.player.player_number,
                    "llm_api_call",
                    f"LLM API returned empty response for Player {self.player.player_number}. Model: {self.model}, Max tokens: {max_tokens}, Finish reason: {response.choices[0].finish_reason}, Usage: {response.usage}"
                )
            
            return content
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
    
    def _analyze_voting_patterns(self, context: AgentContext) -> Dict[str, Any]:
        """
        Analyze voting patterns to identify suspicious behavior.
        
        Args:
            context: Current game context
            
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "suspicious_voters": [],
            "coordinated_votes": [],
            "vote_targets": defaultdict(int)
        }
        
        # Analyze votes from previous days
        for day, votes in context.game_state.votes.items():
            if day < context.game_state.day_number:
                # Count who voted for whom
                for voter, target in votes.items():
                    analysis["vote_targets"][target] += 1
                    self.voting_patterns[voter].append(target)
        
        # Find players who consistently vote together (possible mafia coordination)
        if len(self.voting_patterns) >= 2:
            for player1, votes1 in self.voting_patterns.items():
                for player2, votes2 in self.voting_patterns.items():
                    if player1 != player2 and player1 < player2:
                        # Check if they voted for same targets
                        common_votes = set(votes1) & set(votes2)
                        if len(common_votes) >= 2:
                            analysis["coordinated_votes"].append((player1, player2))
        
        return analysis
    
    def _identify_suspicious_players(self, context: AgentContext) -> List[int]:
        """
        Identify suspicious players based on game history.
        Only marks players as suspicious when there is actual evidence.
        
        Args:
            context: Current game context
            
        Returns:
            List of suspicious player numbers
        """
        suspicious = set()
        
        # Only mark players as suspicious if we have actual evidence
        # Skip on day 1 when no information has been gathered yet
        if context.game_state.day_number <= 1 and not context.game_state.votes:
            return []  # No suspicious players on day 1
        
        # Players who voted for eliminated civilians (possible mafia)
        for action in context.game_state.action_log:
            if action.get("type") == "player_eliminated":
                eliminated = action.get("data", {}).get("player")
                day = action.get("data", {}).get("day_number")
                if day and eliminated:
                    # Check who voted for this eliminated player
                    votes = context.game_state.votes.get(day, {})
                    for voter, target in votes.items():
                        if target == eliminated:
                            eliminated_player = context.game_state.get_player(eliminated)
                            if eliminated_player and eliminated_player.is_civilian:
                                suspicious.add(voter)
        
        # Don't mark players as suspicious just for not being nominated
        # Only use actual voting evidence
        
        return list(suspicious)
    
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
            "- Games typically end in 2-4 rounds, so early decisions are critical",
            "- Night kills account for ~50% of eliminations - they are very powerful",
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
                    "- Your check results:",
                ])
                for night in sorted(self.player.don_checks.keys()):
                    check_data = self.player.don_checks[night]
                    if isinstance(check_data, dict):
                        # New format: {"target": player_num, "result": "Sheriff"/"Not the Sheriff"}
                        target = check_data.get("target", "?")
                        result = check_data.get("result", "?")
                        prompt_parts.append(f"  Night {night}: Player {target} is {result}")
                    else:
                        # Old format: just "Sheriff"/"Not the Sheriff" (backward compatibility)
                        prompt_parts.append(f"  Night {night}: {check_data}")
                prompt_parts.append("")
                prompt_parts.append("DON STRATEGY:")
                prompt_parts.append("- Prioritize checking players who seem to be leading or coordinating")
                prompt_parts.append("- Check players who haven't been checked yet")
                prompt_parts.append("")
        
        if self.player.role.role_type == RoleType.SHERIFF:
            prompt_parts.extend([
                "SHERIFF ABILITIES:",
                "- Check one player per night to see if they are Red (civilian) or Black (mafia)",
                "- Your check results:",
            ])
            for night in sorted(self.player.sheriff_checks.keys()):
                check_data = self.player.sheriff_checks[night]
                if isinstance(check_data, dict):
                    # New format: {"target": player_num, "result": "Red"/"Black"}
                    target = check_data.get("target", "?")
                    result = check_data.get("result", "?")
                    prompt_parts.append(f"  Night {night}: Player {target} is {result}")
                else:
                    # Old format: just "Red"/"Black" (backward compatibility)
                    prompt_parts.append(f"  Night {night}: {check_data}")
            prompt_parts.append("")
            prompt_parts.append("SHERIFF STRATEGY:")
            prompt_parts.append("- Check suspicious players (those who voted for eliminated civilians)")
            prompt_parts.append("- Check players who avoid nominations or seem to be hiding")
            prompt_parts.append("- Don't check randomly - use information from voting patterns")
            prompt_parts.append("")
        
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
        
        prompt_parts.extend([
            "ALIVE PLAYERS:",
        ])
        for player in alive_players:
            status = ""
            if player.player_number in self.suspicious_players:
                status = " [SUSPICIOUS]"
            elif player.player_number in self.trusted_players:
                status = " [TRUSTED]"
            prompt_parts.append(f"  Player {player.player_number}{status}")
        prompt_parts.append("")
        
        # Add voting pattern analysis (only for day/voting phases, skip for night actions)
        if context.current_phase in [GamePhase.DAY, GamePhase.VOTING]:
            analysis = self._analyze_voting_patterns(context)
            suspicious_players = self._identify_suspicious_players(context)
            
            if suspicious_players:
                prompt_parts.append("SUSPICIOUS PLAYERS (based on voting patterns):")
                for player_num in suspicious_players:
                    prompt_parts.append(f"  Player {player_num}")
                prompt_parts.append("")
            
            if analysis["coordinated_votes"]:
                prompt_parts.append("COORDINATED VOTING PATTERNS (possible mafia):")
                for p1, p2 in analysis["coordinated_votes"][:3]:  # Show top 3
                    prompt_parts.append(f"  Players {p1} and {p2} voted together multiple times")
                prompt_parts.append("")
        
        # Add recent history (limit to keep prompt shorter for gpt-5-mini)
        # For night actions, use even less history to save tokens
        if action_type in ["kill_claim", "kill_decision", "sheriff_check", "don_check"]:
            # Night actions need minimal history - just eliminations
            prompt_parts.append("RECENT ELIMINATIONS:")
            recent_history = context.public_history[-5:]  # Last 5 events only
            eliminations = [e for e in recent_history if e.get("type") == "elimination"]
            for event in eliminations[:3]:  # Max 3 eliminations
                reason = event.get('reason', 'unknown')
                prompt_parts.append(f"  Player {event['player']} eliminated ({reason})")
            if not eliminations:
                prompt_parts.append("  None yet")
            prompt_parts.append("")
        else:
            # Day actions can have more history
            prompt_parts.append("RECENT GAME HISTORY:")
            recent_history = context.public_history[-8:]  # Last 8 events
            for event in recent_history:
                if event["type"] == "speech":
                    # Show full speech with timestamp
                    day = event.get('day', context.game_state.day_number)
                    timestamp = event.get('timestamp', f'Day {day}')
                    prompt_parts.append(f"  {timestamp}: Player {event['player']} said: {event['speech']}")
                elif event["type"] == "nomination":
                    prompt_parts.append(f"  Day {event['day']}: Player {event['target']} was nominated")
                elif event["type"] == "elimination":
                    reason = event.get('reason', 'unknown')
                    prompt_parts.append(f"  Player {event['player']} was eliminated ({reason})")
                elif event["type"] == "votes":
                    votes_summary = f"{len(event['votes'])} votes cast"
                    prompt_parts.append(f"  Day {event['day']}: {votes_summary}")
            prompt_parts.append("")
        
        # Add phase-specific instructions
        if action_type == "final_speech":
            prompt_parts.extend([
                "FINAL SPEECH:",
                "- You have been eliminated from the game",
                "- This is your final opportunity to speak",
                "- You can share your thoughts, accuse others, or reveal information",
                "- End your speech with 'PASS' or 'THANK YOU'",
                "",
                "Generate your final speech:",
            ])
        elif action_type == "speech":
            nominations = context.game_state.nominations.get(context.game_state.day_number, [])
            prompt_parts.extend([
                "YOUR TURN TO SPEAK:",
                "- You have up to 200 words",
                "- You can nominate a player by saying 'I nominate player number X'",
                "- End your speech with 'PASS' or 'THANK YOU'",
                "- Analyze voting patterns and suspicious behavior",
                "- If you're sheriff, be careful not to reveal your role",
                "- Coordinate with your team if possible",
                f"- Current nominations: {nominations}",
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
        
        # _call_llm will raise LLMEmptyResponseError if response is empty
        response = self._call_llm(prompt, max_tokens=self.config.max_speech_tokens)
        
        # Ensure speech ends with PASS or THANK YOU
        if not (response.upper().endswith("PASS") or response.upper().endswith("THANK YOU")):
            response += " PASS"
        
        return response
    
    def get_final_speech(self, context: AgentContext) -> str:
        """
        Generate final speech when eliminated.
        
        Args:
            context: Current game context
            
        Returns:
            The final speech text
        """
        prompt = self.build_strategic_prompt(context, "final_speech")
        
        # _call_llm will raise LLMEmptyResponseError if response is empty
        response = self._call_llm(prompt, max_tokens=self.config.max_speech_tokens)
        
        # Ensure speech ends with PASS or THANK YOU
        if not (response.upper().endswith("PASS") or response.upper().endswith("THANK YOU")):
            response += " PASS"
        
        return response
    
    def get_night_action(self, context: AgentContext) -> Dict[str, Any]:
        """
        Get strategic night action using LLM.
        
        Args:
            context: Current game context
            
        Returns:
            Dictionary containing action type and target
        """
        action = {}
        
        # Check if this is a kill decision call (Don or mafia when Don is eliminated)
        # process_mafia_kill sets _kill_decision_context = True to mark it as a kill decision call
        kill_claims = context.private_info.get("mafia_kill_claims", {})
        is_kill_decision_context = context.private_info.get("_kill_decision_context", False)
        alive_player_numbers = {p.player_number for p in context.game_state.get_alive_players()}
        
        if is_kill_decision_context:
            # Explicitly marked as kill decision call by process_mafia_kill
            is_kill_decision_call = True
        elif isinstance(kill_claims, dict):
            keys = list(kill_claims.keys())
            if len(keys) == 0:
                # Empty dict from get_private_info() means no previous nights - NOT a kill decision call
                is_kill_decision_call = False
            else:
                all_keys_are_players = all(k in alive_player_numbers for k in keys)
                keys_sorted = sorted(keys)
                looks_like_night_numbers = keys_sorted == list(range(1, len(keys) + 1))
                # If keys are player numbers (not night numbers), it's from process_mafia_kill
                is_kill_decision_call = all_keys_are_players and not looks_like_night_numbers
        else:
            is_kill_decision_call = False
        
        # Sheriff: Strategic check
        if self.player.role.role_type == RoleType.SHERIFF:
            if not is_kill_decision_call:
                prompt = self.build_strategic_prompt(context, "sheriff_check")
                response = self._call_llm(prompt, max_tokens=self.config.max_action_tokens)
                
                target = self._extract_player_number(response, context)
                if target and target != self.player.player_number:
                    action["type"] = "sheriff_check"
                    action["target"] = target
                    self.checked_players.add(target)
                else:
                    # Fallback: check suspicious player or random
                    suspicious = self._identify_suspicious_players(context)
                    alive_players = context.game_state.get_alive_players()
                    available = [p.player_number for p in alive_players 
                                if p.player_number != self.player.player_number 
                                and p.player_number not in self.checked_players]
                    
                    if suspicious and any(s in available for s in suspicious):
                        target = next(s for s in suspicious if s in available)
                    elif available:
                        target = available[0]  # Simple fallback
                    else:
                        return action
                    
                    action["type"] = "sheriff_check"
                    action["target"] = target
                    self.checked_players.add(target)
        
        # Mafia: Kill claim or decision (but NOT Don - Don is handled separately below)
        if self.player.is_mafia and self.player.role.role_type != RoleType.DON:
            # Check if Don is eliminated and we need to make decision
            if is_kill_decision_call:
                don = next((p for p in context.game_state.get_mafia_players() 
                           if p.role.role_type == RoleType.DON and p.is_alive), None)
                
                if not don and "decide_kill" in context.available_actions:
                    prompt = self.build_strategic_prompt(context, "kill_decision")
                    response = self._call_llm(prompt, max_tokens=self.config.max_action_tokens)
                    
                    target = self._extract_player_number(response, context)
                    if not target and kill_claims:
                        # Fallback: use first claim
                        target = list(kill_claims.values())[0]
                    elif not target:
                        # Fallback: kill random civilian
                        civilians = context.game_state.get_civilian_players()
                        if civilians:
                            target = civilians[0].player_number
                    
                    if target:
                        action["kill_decision"] = target
                        action["type"] = "kill_decision"
            elif not is_kill_decision_call:
                # Normal kill claim
                prompt = self.build_strategic_prompt(context, "kill_claim")
                response = self._call_llm(prompt, max_tokens=self.config.max_action_tokens)
                
                target = self._extract_player_number(response, context)
                if not target:
                    # Fallback: target active players or random
                    civilians = context.game_state.get_civilian_players()
                    if civilians:
                        # Prefer targeting players who have been nominated (active)
                        nominated = set()
                        for day_noms in context.game_state.nominations.values():
                            nominated.update(day_noms)
                        
                        active_civilians = [p for p in civilians if p.player_number in nominated]
                        if active_civilians:
                            target = active_civilians[0].player_number
                        else:
                            target = civilians[0].player_number
                
                if target:
                    action["type"] = "kill_claim"
                    action["target"] = target
        
        # Don: Check and kill decision (handled separately to prioritize don_check over kill_claim)
        if self.player.role.role_type == RoleType.DON:
            # Priority 1: Don check (if this is a don check call, not kill decision)
            if (not is_kill_decision_call and 
                "don_check" in context.available_actions and
                context.game_state.night_number not in self.player.don_checks):
                
                prompt = self.build_strategic_prompt(context, "don_check")
                response = self._call_llm(prompt, max_tokens=self.config.max_action_tokens)
                
                target = self._extract_player_number(response, context)
                if not target:
                    # Fallback: check active players
                    civilians = context.game_state.get_civilian_players()
                    available = [p.player_number for p in civilians 
                                if p.player_number not in self.checked_players]
                    
                    if available:
                        # Prefer checking nominated players (active)
                        nominated = set()
                        for day_noms in context.game_state.nominations.values():
                            nominated.update(day_noms)
                        
                        active_available = [p for p in available if p in nominated]
                        if active_available:
                            target = active_available[0]
                        else:
                            target = available[0]
                
                if target:
                    action["type"] = "don_check"
                    action["target"] = target
                    self.checked_players.add(target)
            
            # Priority 2: Kill decision (when called with kill claims in context)
            if is_kill_decision_call and "decide_kill" in context.available_actions:
                prompt = self.build_strategic_prompt(context, "kill_decision")
                response = self._call_llm(prompt, max_tokens=self.config.max_action_tokens)
                
                target = self._extract_player_number(response, context)
                if not target and kill_claims:
                    # Fallback: use first claim
                    target = list(kill_claims.values())[0]
                elif not target:
                    # Fallback: kill random civilian
                    civilians = context.game_state.get_civilian_players()
                    if civilians:
                        target = civilians[0].player_number
                
                if target:
                    action["kill_decision"] = target
                    action["type"] = "kill_decision"
            
            # Priority 3: Kill claim (only if we haven't already set don_check or kill_decision)
            # Don also makes a kill claim like other mafia during the kill claim phase
            if (not is_kill_decision_call and 
                action.get("type") not in ["don_check", "kill_decision"]):
                prompt = self.build_strategic_prompt(context, "kill_claim")
                response = self._call_llm(prompt, max_tokens=self.config.max_action_tokens)
                
                target = self._extract_player_number(response, context)
                if not target:
                    # Fallback: target active players or random
                    civilians = context.game_state.get_civilian_players()
                    if civilians:
                        # Prefer targeting players who have been nominated (active)
                        nominated = set()
                        for day_noms in context.game_state.nominations.values():
                            nominated.update(day_noms)
                        
                        active_civilians = [p for p in civilians if p.player_number in nominated]
                        if active_civilians:
                            target = active_civilians[0].player_number
                        else:
                            target = civilians[0].player_number
                
                if target:
                    action["type"] = "kill_claim"
                    action["target"] = target
        
        return action
    
    async def get_vote_choice_async(self, context: AgentContext) -> int:
        """
        Async version of get_vote_choice for parallel execution.
        
        Args:
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
        
        prompt = self.build_strategic_prompt(context, "vote")
        response = await self._call_llm_async(prompt, max_tokens=self.config.max_action_tokens)
        
        target = self._extract_player_number(response, context)
        
        # Verify target is in nominations
        if target and target in nominations:
            return target
        
        # Fallback: vote for suspicious player or first nomination
        suspicious = self._identify_suspicious_players(context)
        suspicious_nominated = [n for n in nominations if n in suspicious]
        
        if suspicious_nominated:
            return suspicious_nominated[0]
        
        return nominations[0]
    
    def get_vote_choice(self, context: AgentContext) -> int:
        """
        Get strategic vote choice using LLM (synchronous version).
        
        Args:
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
        
        prompt = self.build_strategic_prompt(context, "vote")
        response = self._call_llm(prompt, max_tokens=self.config.max_action_tokens)
        
        target = self._extract_player_number(response, context)
        
        # Verify target is in nominations
        if target and target in nominations:
            return target
        
        # Fallback: vote for suspicious player or first nomination
        suspicious = self._identify_suspicious_players(context)
        suspicious_nominated = [n for n in nominations if n in suspicious]
        
        if suspicious_nominated:
            return suspicious_nominated[0]
        
        return nominations[0]
