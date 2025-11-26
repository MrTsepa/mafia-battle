"""
Test script for LLM Agent with real OpenAI API calls.
This verifies that the agent can successfully make API calls and process responses.
"""

import os
import sys

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, that's okay

from src.core import GameState, Judge, RoleType
from src.agents import SimpleLLMAgent
from src.config.game_config import GameConfig
from src.config.config_loader import load_config


def test_llm_agent_initialization():
    """Test that LLM agent can be initialized."""
    print("Testing LLM agent initialization...")
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set!")
        return False
    
    print(f"✓ API key found (length: {len(api_key)})")
    
    # Load config
    config = load_config("configs/simple_llm_agent.yaml")
    print(f"✓ Config loaded, model: {config.llm_model}")
    
    # Create game state
    game_state = GameState(random_seed=42)
    judge = Judge(game_state, config)
    
    # Initialize agents
    agents = {}
    for player in game_state.players:
        try:
            agent = SimpleLLMAgent(player, config)
            agents[player.player_number] = agent
            print(f"✓ Agent initialized for Player {player.player_number} ({player.role.role_type.value})")
        except Exception as e:
            print(f"✗ Failed to initialize agent for Player {player.player_number}: {e}")
            return False
    
    print(f"✓ All {len(agents)} agents initialized successfully\n")
    return True, agents, game_state, judge, config


def test_llm_speech(agents, game_state, judge):
    """Test that LLM agent can generate a speech."""
    print("Testing LLM speech generation...")
    
    game_state.start_day()
    agent = agents[1]  # Use first player
    context = agent.build_context(game_state)
    
    try:
        speech = agent.get_day_speech(context)
        print(f"✓ Speech generated: {speech[:100]}...")
        print(f"  Length: {len(speech)} characters")
        if "PASS" in speech.upper() or "THANK YOU" in speech.upper():
            print("  ✓ Speech ends with PASS/THANK YOU")
        else:
            print("  ⚠ Speech doesn't end with PASS/THANK YOU")
        print()
        return True
    except Exception as e:
        print(f"✗ Failed to generate speech: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_night_action(agents, game_state, judge):
    """Test that LLM agent can generate night actions."""
    print("Testing LLM night action generation...")
    
    game_state.start_night()
    
    # Test sheriff check
    sheriff = next((p for p in game_state.players if p.role.role_type == RoleType.SHERIFF), None)
    if sheriff:
        agent = agents[sheriff.player_number]
        context = agent.build_context(game_state)
        try:
            action = agent.get_night_action(context)
            print(f"✓ Sheriff action: {action}")
            if action.get("type") == "sheriff_check":
                print(f"  ✓ Checking player {action.get('target')}")
            print()
        except Exception as e:
            print(f"✗ Failed to generate sheriff action: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Test mafia kill claim
    mafia = next((p for p in game_state.get_mafia_players() if p.role.role_type != RoleType.DON), None)
    if mafia:
        agent = agents[mafia.player_number]
        context = agent.build_context(game_state)
        try:
            action = agent.get_night_action(context)
            print(f"✓ Mafia action: {action}")
            if action.get("type") == "kill_claim":
                print(f"  ✓ Claiming to kill player {action.get('target')}")
            print()
        except Exception as e:
            print(f"✗ Failed to generate mafia action: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Test Don check and kill decision
    don = next((p for p in game_state.get_mafia_players() if p.role.role_type == RoleType.DON), None)
    if don:
        agent = agents[don.player_number]
        context = agent.build_context(game_state)
        try:
            action = agent.get_night_action(context)
            print(f"✓ Don action: {action}")
            if "don_check" in action.get("type", ""):
                print(f"  ✓ Don checking player {action.get('target')}")
            print()
        except Exception as e:
            print(f"✗ Failed to generate Don action: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


def test_llm_vote(agents, game_state, judge):
    """Test that LLM agent can generate vote choice."""
    print("Testing LLM vote choice generation...")
    
    game_state.start_day()
    game_state.nominations[game_state.day_number] = [2, 3, 4]  # Add some nominations
    game_state.start_voting()
    
    agent = agents[1]
    context = agent.build_context(game_state)
    
    try:
        vote = agent.get_vote_choice(context)
        print(f"✓ Vote choice: Player {vote}")
        if vote in game_state.nominations[game_state.day_number]:
            print(f"  ✓ Vote is for a nominated player")
        else:
            print(f"  ⚠ Vote is not for a nominated player")
        print()
        return True
    except Exception as e:
        print(f"✗ Failed to generate vote: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_quick_game_simulation(agents, game_state, judge, config):
    """Run a quick game simulation to test full integration."""
    print("Testing quick game simulation (2 rounds max)...")
    
    from src.phases import DayPhaseHandler, VotingHandler, NightPhaseHandler
    
    day_handler = DayPhaseHandler(game_state, judge)
    voting_handler = VotingHandler(game_state, judge)
    night_handler = NightPhaseHandler(game_state, judge)
    
    max_rounds = 2
    rounds = 0
    
    try:
        while rounds < max_rounds:
            rounds += 1
            print(f"\n--- Round {rounds} ---")
            
            # Day phase
            game_state.start_day()
            print(f"Day {game_state.day_number} started")
            
            # Get speaking order
            speaking_order = day_handler.get_speaking_order()
            print(f"Speaking order: {speaking_order[:3]}... (showing first 3)")
            
            # Process a few speeches (limit to avoid too many API calls)
            speeches_processed = 0
            for player_num in speaking_order[:3]:  # Only first 3 players
                if speeches_processed >= 3:
                    break
                agent = agents[player_num]
                context = agent.build_context(game_state)
                speech = agent.get_day_speech(context)
                print(f"  Player {player_num} speech: {speech[:60]}...")
                speeches_processed += 1
            
            # Check win condition
            winner = game_state.check_win_condition()
            if winner:
                print(f"Game ended: {winner} wins!")
                break
            
            # Voting phase (skip for quick test)
            print("Skipping voting phase for quick test")
            
            # Night phase
            game_state.start_night()
            print(f"Night {game_state.night_number} started")
            
            # Process mafia kill
            killed = night_handler.process_mafia_kill(agents)
            if killed:
                print(f"  Player {killed} was killed")
                game_state.eliminate_player(killed, "night kill", night_number=game_state.night_number)
            
            # Check win condition
            winner = game_state.check_win_condition()
            if winner:
                print(f"Game ended: {winner} wins!")
                break
        
        print(f"\n✓ Simulation completed ({rounds} rounds)")
        return True
        
    except Exception as e:
        print(f"✗ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("LLM Agent Test Suite")
    print("=" * 60)
    print()
    
    # Test initialization
    result = test_llm_agent_initialization()
    if not result:
        print("Initialization failed, aborting tests")
        return 1
    
    success, agents, game_state, judge, config = result
    
    # Run tests
    tests = [
        ("Speech Generation", lambda: test_llm_speech(agents, game_state, judge)),
        ("Night Actions", lambda: test_llm_night_action(agents, game_state, judge)),
        ("Vote Choice", lambda: test_llm_vote(agents, game_state, judge)),
        ("Quick Game Simulation", lambda: test_quick_game_simulation(agents, game_state, judge, config)),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"Test: {test_name}")
        print('=' * 60)
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

