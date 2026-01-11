"""
Voting system with tie-breaking logic.
"""

import asyncio
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from ..core import GameState, Judge
from ..agents import BaseAgent, SimpleLLMAgent

if TYPE_CHECKING:
    from ..web.event_emitter import EventEmitter


class VotingHandler:
    """Handles voting phase and tie-breaking."""
    
    def __init__(self, game_state: GameState, judge: Judge, event_emitter: Optional['EventEmitter'] = None):
        self.game_state = game_state
        self.judge = judge
        self.event_emitter = event_emitter
        self.tie_break_round = 0
        self.last_tie_break_voters: List[int] = []
    
    async def collect_votes_async(self, agents: dict[int, BaseAgent]) -> None:
        """
        Collect votes from all alive players in parallel (async version).
        """
        nominations = self.judge.get_nominated_players()
        
        if not nominations:
            return
        
        # Emit voting start event
        if self.event_emitter:
            self.event_emitter.emit_voting_start(nominations, self.game_state.day_number)
        
        self.judge.announce(f"Players {nominations} have been nominated. I repeat, {nominations}, in this order.")
        self.judge.announce("You must vote. If you don't vote, your vote will count for the last person nominated.")
        
        # Single voting call
        self.judge.announce("Who votes...")
        
        # Collect votes from all alive players in parallel
        async def get_vote_for_player(player_num: int, agent: BaseAgent) -> tuple[int, int, Optional[Dict[str, Any]]]:
            """Get vote choice for a single player."""
            context = agent.build_context(self.game_state)
            
            # Capture context for LLM agents
            context_data = None
            if hasattr(agent, 'build_strategic_prompt'):
                try:
                    prompt = agent.build_strategic_prompt(context, "vote")
                    context_data = {
                        "prompt": prompt,
                        "player_role": agent.player.role.role_type.value,
                        "player_team": agent.player.role.team.value
                    }
                except:
                    pass
            
            # Use async version if available (SimpleLLMAgent), otherwise fallback to sync
            if isinstance(agent, SimpleLLMAgent):
                vote_choice = await agent.get_vote_choice_async(context)
            else:
                vote_choice = agent.get_vote_choice(context)
            
            # Add reasoning to context_data if available (after LLM call)
            if context_data and hasattr(agent, 'last_reasoning') and agent.last_reasoning:
                context_data["reasoning"] = agent.last_reasoning
            
            return player_num, vote_choice, context_data
        
        # Create tasks for all players
        tasks = []
        for player in self.game_state.get_alive_players():
            if player.player_number in agents:
                agent = agents[player.player_number]
                tasks.append(get_vote_for_player(player.player_number, agent))
                
        # Wait for all votes in parallel
        if tasks:
            results = await asyncio.gather(*tasks)
                
            # Process all votes
            for player_num, vote_choice, context_data in results:
                # Safety check: prevent self-voting
                if vote_choice == player_num:
                    # Reject self-vote, fallback to first other nomination
                    valid_nominations = [n for n in nominations if n != player_num]
                    if valid_nominations:
                        vote_choice = valid_nominations[0]
                    else:
                        # If only self is nominated, skip this vote (shouldn't happen)
                        continue
                
                if vote_choice in nominations:
                    self.judge.process_vote(player_num, vote_choice)
                    # Emit vote event
                    if self.event_emitter:
                        self.event_emitter.emit_vote(player_num, vote_choice, self.game_state.day_number, context_data)
    
    def collect_votes(self, agents: dict[int, BaseAgent]) -> None:
        """
        Collect votes from all alive players (synchronous version, uses async internally).
        """
        # Run async version in sync context
        asyncio.run(self.collect_votes_async(agents))
    
    def process_voting(self, agents: dict[int, BaseAgent]) -> Optional[int]:
        """
        Process voting and return eliminated player number, or None if tie needs resolution.
        """
        self.collect_votes(agents)
        
        # Get vote counts
        counts = self.judge.get_vote_counts()
        
        if not counts:
            return None
        
        # Get who voted for whom
        day = self.game_state.day_number
        votes = self.game_state.votes.get(day, {})
        
        # Find non-voters (they get default vote for last nominated)
        nominations = self.judge.get_nominated_players()
        alive_players = [p.player_number for p in self.game_state.get_alive_players()]
        voters_set = set(votes.keys())
        non_voters = [p for p in alive_players if p not in voters_set]
        last_nominated = nominations[-1] if nominations else None
        
        # Build voters dict for event emission
        voters_dict = {}
        for player, vote_count in counts.items():
            # Find who voted for this player
            voters = [voter for voter, target in votes.items() if target == player]
            
            # Add non-voters if this is the last nominated player
            if player == last_nominated and non_voters:
                voters.extend(non_voters)
            
            voters_dict[player] = voters
            self.judge.announce(f"{vote_count} votes for player {player}, voted: {voters}")
        
        # Emit vote results event
        if self.event_emitter:
            self.event_emitter.emit_vote_results(counts, voters_dict, self.game_state.day_number)
        
        # Check for elimination
        target = self.judge.get_elimination_target()
        
        if target:
            # Clear winner
            return target
        
        # Tie detected
        return None

    def _get_voters_for_target(self, target: int) -> List[int]:
        """Get all voters for a target, including default votes from non-voters."""
        day = self.game_state.day_number
        votes = self.game_state.votes.get(day, {})
        voters = [voter for voter, voted_target in votes.items() if voted_target == target]
        nominations = self.judge.get_nominated_players()
        if nominations:
            last_nominated = nominations[-1]
            if target == last_nominated:
                alive_players = [p.player_number for p in self.game_state.get_alive_players()]
                voters_set = set(votes.keys())
                non_voters = [p for p in alive_players if p not in voters_set]
                voters.extend(non_voters)
        return voters
    
    def handle_tie(self, tied_players: List[int], agents: dict[int, BaseAgent]) -> Optional[List[int]]:
        """
        Handle tie-breaking procedure.
        Returns eliminated players or None if all remain.
        """
        self.tie_break_round += 1
        self.last_tie_break_voters = []
        
        # Emit tie event
        if self.event_emitter:
            self.event_emitter.emit_tie(tied_players, self.game_state.day_number)
        
        self.judge.announce(f"Tie detected between players {tied_players}.")
        self.judge.announce("Tied players will each get an additional speech, then we will revote.")
        
        # Tied players get additional speeches (shorter limit)
        for player_number in tied_players:
            if player_number in agents:
                agent = agents[player_number]
                player = self.game_state.get_player(player_number)
                
                if not player or not player.is_alive:
                    continue
                
                self.judge.announce(f"Player {player_number}, you have 30 seconds (reduced word limit) to speak.")
                
                context = agent.build_context(self.game_state)
                speech = agent.get_day_speech(context)
                
                # Token limits are handled by LLM configuration (unlimited by default)
                # No word-based truncation needed
                
                if not self.judge.validate_speech_ending(speech):
                    speech += " PASS"
                
                player.add_speech(speech)
                self.judge.player_speaks(player_number, speech)
        
        # Restrict nominations to only tied players for the revote
        day = self.game_state.day_number
        
        # Set nominations to only tied players for the revote
        self.game_state.nominations[day] = tied_players.copy()
        
        # Clear previous votes for this day to start fresh
        if day in self.game_state.votes:
            self.game_state.votes[day] = {}
        
        # Revote - now only between tied players (all players must still vote)
        self.judge.announce(f"Revote: You must vote between players {tied_players} only.")
        self.judge.start_voting()
        target = self.process_voting(agents)
        
        if target:
            return [target]
        
        # Still a tie - check if same players or fewer
        new_tied = self.judge.get_tied_players()
        
        if set(new_tied) == set(tied_players):
            # Same tie - vote to eliminate all or keep all
            return self._vote_eliminate_all(tied_players, agents)
        elif len(new_tied) < len(tied_players):
            # Fewer players tied - continue tie-breaking
            return self.handle_tie(new_tied, agents)
        
        return None
    
    async def _vote_eliminate_all_async(self, tied_players: List[int], agents: dict[int, BaseAgent]) -> Optional[List[int]]:
        """
        Vote to eliminate all tied players or keep all (async version).
        Returns eliminated players or None.
        """
        self.judge.announce(f"Same tie persists. Vote: Who is in favour of all nominated players ({tied_players}) leaving the game?")
        
        # Collect votes in parallel
        async def get_vote_for_player(player_num: int, agent: BaseAgent) -> tuple[int, int, Optional[Dict[str, Any]]]:
            """Get vote choice for a single player."""
            context = agent.build_context(self.game_state)
            
            # Capture context for LLM agents
            context_data = None
            if hasattr(agent, 'build_strategic_prompt'):
                try:
                    prompt = agent.build_strategic_prompt(context, "vote")
                    context_data = {
                        "prompt": prompt,
                        "player_role": agent.player.role.role_type.value,
                        "player_team": agent.player.role.team.value
                    }
                except:
                    pass
            
            # Use async version if available (SimpleLLMAgent), otherwise fallback to sync
            if isinstance(agent, SimpleLLMAgent):
                vote = await agent.get_vote_choice_async(context)
            else:
                vote = agent.get_vote_choice(context)
            
            # Add reasoning to context_data if available (after LLM call)
            if context_data and hasattr(agent, 'last_reasoning') and agent.last_reasoning:
                context_data["reasoning"] = agent.last_reasoning
            
            return player_num, vote, context_data
        
        # Create tasks for all players
        tasks = []
        for player in self.game_state.get_alive_players():
            if player.player_number in agents:
                agent = agents[player.player_number]
                tasks.append(get_vote_for_player(player.player_number, agent))
                
        # Wait for all votes in parallel
        votes_for_elimination = 0
        votes_against = 0
        voters_for_elimination: List[int] = []
        
        if tasks:
            results = await asyncio.gather(*tasks)
            
            for player_num, vote, context_data in results:
                # If agent votes for any tied player, count as "eliminate all"
                if vote in tied_players:
                    votes_for_elimination += 1
                    voters_for_elimination.append(player_num)
                else:
                    votes_against += 1
        
        total_votes = votes_for_elimination + votes_against
        majority = total_votes / 2
        
        if votes_for_elimination > majority:
            # All tied players eliminated
            self.judge.announce(f"Majority votes to eliminate all. Players {tied_players} are eliminated.")
            self.last_tie_break_voters = voters_for_elimination
            return tied_players
        elif votes_for_elimination == votes_against:
            # Split vote - all remain
            self.judge.announce("Vote splits evenly. All tied players remain in the game.")
            return None
        else:
            # Keep all
            self.judge.announce("Majority votes to keep all. All tied players remain in the game.")
            return None
    
    def _vote_eliminate_all(self, tied_players: List[int], agents: dict[int, BaseAgent]) -> Optional[List[int]]:
        """
        Vote to eliminate all tied players or keep all (synchronous wrapper).
        Returns eliminated players or None.
        """
        return asyncio.run(self._vote_eliminate_all_async(tied_players, agents))
    
    def run_voting_phase(self, agents: dict[int, BaseAgent]) -> None:
        """
        Run complete voting phase with tie-breaking if needed.
        """
        target = self.process_voting(agents)
        
        if target:
            voters = self._get_voters_for_target(target)
            
            self.game_state.eliminate_player(
                target, 
                "voting",
                day_number=self.game_state.day_number,
                voters=voters
            )
            player = self.game_state.get_player(target)
            if player and target in agents:
                self.judge.announce(f"Player {target} has been eliminated. This is your final speech.")
                # Collect final speech from eliminated player
                agent = agents[target]
                context = agent.build_context(self.game_state)
                final_speech = agent.get_final_speech(context)
                
                # Add to player history
                player.add_speech(final_speech)
                
                # Emit final speech event
                if self.event_emitter:
                    # Capture context for LLM agents
                    context_data = None
                    if isinstance(agent, SimpleLLMAgent):
                        try:
                            prompt = agent.build_strategic_prompt(context, "final_speech")
                            context_data = {
                                "prompt": prompt,
                                "player_role": agent.player.role.role_type.value,
                                "player_team": agent.player.role.team.value
                            }
                        except:
                            pass
                        
                        # Add reasoning to context_data if available (after LLM call)
                        if context_data and hasattr(agent, 'last_reasoning') and agent.last_reasoning:
                            context_data["reasoning"] = agent.last_reasoning
                        
                        self.event_emitter.emit_speech(target, final_speech, self.game_state.day_number, context_data)
        else:
            # Tie - handle tie-breaking
            tied_players = self.judge.get_tied_players()
            if tied_players:
                result = self.handle_tie(tied_players, agents)
                if result:
                    eliminated_players = result
                    voters = self.last_tie_break_voters
                    if len(eliminated_players) == 1:
                        voters = self._get_voters_for_target(eliminated_players[0])
                    
                    for eliminated_player in eliminated_players:
                        self.game_state.eliminate_player(
                            eliminated_player, 
                            "tie-break vote",
                            day_number=self.game_state.day_number,
                            voters=voters
                        )
                        player = self.game_state.get_player(eliminated_player)
                        if player and eliminated_player in agents:
                            self.judge.announce(f"Player {eliminated_player} has been eliminated. This is your final speech.")
                            agent = agents[eliminated_player]
                            context = agent.build_context(self.game_state)
                            final_speech = agent.get_final_speech(context)
                            player.add_speech(final_speech)
                            if self.event_emitter:
                                context_data = None
                                if isinstance(agent, SimpleLLMAgent):
                                    try:
                                        prompt = agent.build_strategic_prompt(context, "final_speech")
                                        context_data = {
                                            "prompt": prompt,
                                            "player_role": agent.player.role.role_type.value,
                                            "player_team": agent.player.role.team.value
                                        }
                                    except:
                                        pass
                                
                                # Add reasoning to context_data if available (after LLM call)
                                if context_data and hasattr(agent, 'last_reasoning') and agent.last_reasoning:
                                    context_data["reasoning"] = agent.last_reasoning
                                
                                self.event_emitter.emit_speech(eliminated_player, final_speech, self.game_state.day_number, context_data)
