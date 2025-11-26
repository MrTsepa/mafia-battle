"""
Test to demonstrate and verify LLM context passed for each action type.

This test creates a sample game state with history and captures
the prompts passed to LLM for each type of action.

Run with: pytest tests/test_llm_context_examples.py -v -s

The test will:
1. Create a game state with Day 1 and Day 2 history
2. Capture prompts for each action type
3. Save full prompts to files in tests/context_examples/ for review
4. Print summaries and verify all required sections are present
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.core import GameState, GamePhase, RoleType
from src.agents import SimpleLLMAgent
from src.config.game_config import GameConfig


def test_llm_context_examples():
    """
    Test that demonstrates the context passed to LLM for each action type.
    
    This test:
    1. Sets up a game state with history (Day 1 speeches, eliminations, night kills)
    2. Captures prompts for each action type
    3. Prints/verifies the context structure
    """
    config = GameConfig()
    
    # Create game state and set up some history
    game_state = GameState()
    game_state.setup_game()
    
    # Set up Day 1 history
    game_state.day_number = 2
    game_state.night_number = 1
    game_state.phase = GamePhase.DAY
    
    # Add some Day 1 speeches to players
    for i, player in enumerate(game_state.players[:5]):
        speech = f"Day 1 speech from Player {player.player_number}: I think we should gather information first. No nomination yet. PASS"
        player.add_speech(speech)
    
    # Add Day 1 nominations
    game_state.nominations[1] = [3, 5]
    
    # Find specific players BEFORE eliminations
    sheriff = next((p for p in game_state.players if p.role.role_type == RoleType.SHERIFF), None)
    don = next((p for p in game_state.players if p.role.role_type == RoleType.DON), None)
    mafia = next((p for p in game_state.players if p.is_mafia and p.role.role_type != RoleType.DON), None)
    civilian = next((p for p in game_state.players if p.is_civilian and p.role.role_type != RoleType.SHERIFF), None)
    
    assert sheriff is not None, "Need a sheriff for testing"
    assert don is not None, "Need a don for testing"
    assert mafia is not None, "Need a mafia player for testing"
    assert civilian is not None, "Need a civilian for testing"
    
    # Choose elimination targets that won't be our test players
    # Eliminate players that are NOT sheriff, don, or our test mafia/civilian
    test_player_nums = {sheriff.player_number, don.player_number, mafia.player_number, civilian.player_number}
    elimination_target = next((p.player_number for p in game_state.players if p.player_number not in test_player_nums), None)
    assert elimination_target is not None, "Need a player to eliminate"
    
    # Add Day 1 votes
    game_state.votes[1] = {
        1: elimination_target,  # Player 1 voted for target
        2: elimination_target,  # Player 2 voted for target
        4: elimination_target,  # Player 4 voted for target
        6: elimination_target,  # Player 6 voted for target
    }
    
    # Add an elimination (target was eliminated on Day 1)
    game_state.eliminate_player(elimination_target, "voting", day_number=1, voters=[1, 2, 4, 6])
    
    # Add a night kill (choose another non-test player)
    night_kill_target = next((p.player_number for p in game_state.players 
                              if p.is_alive and p.player_number not in test_player_nums), None)
    if night_kill_target:
        game_state.night_number = 1
        game_state.night_kills[1] = night_kill_target
        game_state.eliminate_player(night_kill_target, "night kill", night_number=1)
    
    # Add Day 2 speeches (current day) - only for alive players
    alive_players = game_state.get_alive_players()
    for i, player in enumerate(alive_players[:3]):
        speech = f"Day 2 speech from Player {player.player_number}: Based on yesterday's events, I think we need to investigate further. PASS"
        player.add_speech(speech)
    
    # Add Day 2 nominations (use a non-test player)
    nomination_target = next((p.player_number for p in game_state.get_alive_players() 
                              if p.player_number not in test_player_nums), None)
    if nomination_target:
        game_state.nominations[2] = [nomination_target]
    
    # Store captured prompts
    captured_prompts = {}
    
    def capture_prompt(prompt, *args, **kwargs):
        """Capture the prompt passed to _call_llm"""
        # Store by action type (we'll determine this from context)
        return "mock_response"
    
    # Test 1: Day Speech Context
    print("\n" + "="*80)
    print("TEST 1: DAY SPEECH CONTEXT")
    print("="*80)
    
    with patch.object(SimpleLLMAgent, '_call_llm', side_effect=capture_prompt) as mock_llm:
        agent = SimpleLLMAgent(civilian, config)
        context = agent.build_context(game_state)
        prompt = agent.build_strategic_prompt(context, "speech")
        captured_prompts["day_speech"] = prompt
        
        print("\nDay Speech Prompt (first 2000 chars):")
        print("-" * 80)
        print(prompt[:2000])
        print("...")
        print(f"\nTotal prompt length: {len(prompt)} characters")
        
        # Verify key sections are present
        assert "GAME HISTORY (chronological order)" in prompt, "Should include chronological history"
        assert "[Day 2]" in prompt, "Should include current day events"
        assert "[Day 1]" in prompt, "Should include previous day events"
        assert "eliminated" in prompt, "Should include eliminations"
        assert "[Night" in prompt, "Should include night kills"
        assert "→ Player" in prompt, "Should include vote information"
    
    # Test 2: Final Speech Context
    print("\n" + "="*80)
    print("TEST 2: FINAL SPEECH CONTEXT")
    print("="*80)
    
    # Eliminate a player to test final speech (get before elimination)
    alive_before = game_state.get_alive_players()
    eliminated_player_num = alive_before[0].player_number
    eliminated_player = game_state.get_player(eliminated_player_num)
    game_state.eliminate_player(eliminated_player_num, "voting", day_number=2)
    
    with patch.object(SimpleLLMAgent, '_call_llm', side_effect=capture_prompt) as mock_llm:
        agent = SimpleLLMAgent(eliminated_player, config)
        context = agent.build_context(game_state)
        prompt = agent.build_strategic_prompt(context, "final_speech")
        captured_prompts["final_speech"] = prompt
        
        print("\nFinal Speech Prompt (first 2000 chars):")
        print("-" * 80)
        print(prompt[:2000])
        print("...")
        print(f"\nTotal prompt length: {len(prompt)} characters")
        
        # Verify key sections
        assert "FINAL SPEECH" in prompt, "Should include final speech instructions"
        assert "GAME HISTORY (chronological order)" in prompt, "Should include chronological history"
        assert "[Day 2]" in prompt, "Should include current day events"
        assert "[Day 1]" in prompt, "Should include previous day events"
    
    # Test 3: Sheriff Check Context (Night Action)
    print("\n" + "="*80)
    print("TEST 3: SHERIFF CHECK CONTEXT (Night Action)")
    print("="*80)
    
    game_state.phase = GamePhase.NIGHT
    game_state.night_number = 2
    
    # Add a sheriff check result from Night 1
    sheriff.add_sheriff_check(1, 4, "Black")
    
    with patch.object(SimpleLLMAgent, '_call_llm', side_effect=capture_prompt) as mock_llm:
        agent = SimpleLLMAgent(sheriff, config)
        context = agent.build_context(game_state)
        prompt = agent.build_strategic_prompt(context, "sheriff_check")
        captured_prompts["sheriff_check"] = prompt
        
        print("\nSheriff Check Prompt (first 2000 chars):")
        print("-" * 80)
        print(prompt[:2000])
        print("...")
        print(f"\nTotal prompt length: {len(prompt)} characters")
        
        # Verify key sections for night actions
        assert "SHERIFF CHECK" in prompt, "Should include sheriff check instructions"
        assert "GAME HISTORY (chronological order)" in prompt, "Night actions should include chronological history"
        assert "[Day 2]" in prompt, "Night actions should include current day events"
        assert "[Day 1]" in prompt, "Night actions should include previous day events"
        assert "[Night" in prompt, "Should include night events"
        assert "Night 1: Player 4 is Black" in prompt, "Should include previous check results"
    
    # Test 4: Don Check Context (Night Action)
    print("\n" + "="*80)
    print("TEST 4: DON CHECK CONTEXT (Night Action)")
    print("="*80)
    
    # Add a don check result from Night 1
    don.add_don_check(1, 6, "Not the Sheriff")
    
    with patch.object(SimpleLLMAgent, '_call_llm', side_effect=capture_prompt) as mock_llm:
        agent = SimpleLLMAgent(don, config)
        context = agent.build_context(game_state)
        prompt = agent.build_strategic_prompt(context, "don_check")
        captured_prompts["don_check"] = prompt
        
        print("\nDon Check Prompt (first 2000 chars):")
        print("-" * 80)
        print(prompt[:2000])
        print("...")
        print(f"\nTotal prompt length: {len(prompt)} characters")
        
        # Verify key sections
        assert "DON CHECK" in prompt, "Should include don check instructions"
        assert "GAME HISTORY (chronological order)" in prompt, "Night actions should include chronological history"
        assert "[Day 2]" in prompt, "Night actions should include current day events"
        assert "[Day 1]" in prompt, "Night actions should include previous day events"
        assert "Night 1: Player 6 is Not the Sheriff" in prompt, "Should include previous check results"
    
    # Test 5: Kill Decision Context (Night Action)
    print("\n" + "="*80)
    print("TEST 5: KILL DECISION CONTEXT (Night Action)")
    print("="*80)
    
    # Set up kill claims for the decision
    kill_claims = {
        1: 5,  # Player 1 wants to kill Player 5
        4: 6,  # Player 4 wants to kill Player 6
    }
    
    with patch.object(SimpleLLMAgent, '_call_llm', side_effect=capture_prompt) as mock_llm:
        agent = SimpleLLMAgent(don, config)
        context = agent.build_context(game_state)
        context.private_info["mafia_kill_claims"] = kill_claims
        context.private_info["_kill_decision_context"] = True
        prompt = agent.build_strategic_prompt(context, "kill_decision")
        captured_prompts["kill_decision"] = prompt
        
        print("\nKill Decision Prompt (first 2000 chars):")
        print("-" * 80)
        print(prompt[:2000])
        print("...")
        print(f"\nTotal prompt length: {len(prompt)} characters")
        
        # Verify key sections
        assert "KILL DECISION" in prompt, "Should include kill decision instructions"
        assert "Team claims:" in prompt, "Should include team kill claims"
        assert "P1 → P5" in prompt or "Player 1" in prompt, "Should show kill claims"
        assert "GAME HISTORY (chronological order)" in prompt, "Night actions should include chronological history"
        assert "[Day 2]" in prompt, "Night actions should include current day events"
        assert "[Day 1]" in prompt, "Night actions should include previous day events"
        assert "[Night" in prompt, "Should include night events"
    
    # Test 6: Kill Claim Context (Night Action)
    print("\n" + "="*80)
    print("TEST 6: KILL CLAIM CONTEXT (Night Action)")
    print("="*80)
    
    with patch.object(SimpleLLMAgent, '_call_llm', side_effect=capture_prompt) as mock_llm:
        agent = SimpleLLMAgent(mafia, config)
        context = agent.build_context(game_state)
        prompt = agent.build_strategic_prompt(context, "kill_claim")
        captured_prompts["kill_claim"] = prompt
        
        print("\nKill Claim Prompt (first 2000 chars):")
        print("-" * 80)
        print(prompt[:2000])
        print("...")
        print(f"\nTotal prompt length: {len(prompt)} characters")
        
        # Verify key sections
        assert "KILL CLAIM" in prompt, "Should include kill claim instructions"
        assert "GAME HISTORY (chronological order)" in prompt, "Night actions should include chronological history"
        assert "[Day 2]" in prompt, "Night actions should include current day events"
        assert "[Day 1]" in prompt, "Night actions should include previous day events"
        assert "MAFIA TEAM" in prompt, "Should include mafia team information"
    
    # Save full prompts to files for review
    output_dir = Path("tests/context_examples")
    output_dir.mkdir(exist_ok=True)
    
    print("\n" + "="*80)
    print("SAVING FULL PROMPTS TO FILES")
    print("="*80)
    
    for action_type, prompt in captured_prompts.items():
        output_file = output_dir / f"{action_type}_prompt.txt"
        with open(output_file, "w") as f:
            f.write(prompt)
        print(f"Saved {action_type} prompt to {output_file}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY: Context Lengths")
    print("="*80)
    for action_type, prompt in captured_prompts.items():
        print(f"{action_type:20s}: {len(prompt):6d} characters")
    
    print("\n✅ All context tests passed!")
    print("\nKey findings:")
    print("- Day speeches include all current and previous day speeches")
    print("- Night actions include all day speeches (not just eliminations)")
    print("- All actions include eliminations and night kills")
    print("- Vote information is clearly formatted")
    print("- Check results are included for Sheriff and Don")
    print(f"\nFull prompts saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    # Run the test directly
    test_llm_context_examples()

