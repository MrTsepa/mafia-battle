"""
Minimal test script to see real LLM agent outputs.
Tests different scenarios without running full game.
"""

import os
import sys

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core import GameState, Judge, RoleType
from src.agents import SimpleLLMAgent
from src.config.config_loader import load_config


def test_speech_generation():
    """Test LLM speech generation."""
    print("=" * 60)
    print("TEST 1: Day Speech Generation")
    print("=" * 60)
    
    config = load_config("configs/simple_llm_agent.yaml")
    game_state = GameState(random_seed=42)
    judge = Judge(game_state, config)
    
    # Get first player
    player = game_state.players[0]
    agent = SimpleLLMAgent(player, config)
    
    game_state.start_day()
    context = agent.build_context(game_state)
    
    print(f"\nPlayer {player.player_number} ({player.role.role_type.value}) generating speech...")
    print("-" * 60)
    
    try:
        speech = agent.get_day_speech(context)
        print(f"\n✓ Speech generated ({len(speech)} chars):")
        print(f"\n{speech}")
        print("\n" + "-" * 60)
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_night_action_sheriff():
    """Test Sheriff check."""
    print("\n" + "=" * 60)
    print("TEST 2: Sheriff Check (Night Action)")
    print("=" * 60)
    
    config = load_config("configs/simple_llm_agent.yaml")
    game_state = GameState(random_seed=42)
    judge = Judge(game_state, config)
    
    # Find sheriff
    sheriff = next((p for p in game_state.players if p.role.role_type == RoleType.SHERIFF), None)
    if not sheriff:
        print("❌ No sheriff found")
        return False
    
    agent = SimpleLLMAgent(sheriff, config)
    
    game_state.start_night()
    context = agent.build_context(game_state)
    
    print(f"\nSheriff (Player {sheriff.player_number}) choosing check target...")
    print("-" * 60)
    
    try:
        action = agent.get_night_action(context)
        print(f"\n✓ Action generated:")
        print(f"  Type: {action.get('type')}")
        print(f"  Target: {action.get('target')}")
        print("\n" + "-" * 60)
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_night_action_mafia():
    """Test Mafia kill claim."""
    print("\n" + "=" * 60)
    print("TEST 3: Mafia Kill Claim (Night Action)")
    print("=" * 60)
    
    config = load_config("configs/simple_llm_agent.yaml")
    game_state = GameState(random_seed=42)
    judge = Judge(game_state, config)
    
    # Find a mafia (not Don)
    mafia = next((p for p in game_state.get_mafia_players() 
                 if p.role.role_type != RoleType.DON), None)
    if not mafia:
        print("❌ No mafia found")
        return False
    
    agent = SimpleLLMAgent(mafia, config)
    
    game_state.start_night()
    context = agent.build_context(game_state)
    
    print(f"\nMafia (Player {mafia.player_number}) choosing kill target...")
    print(f"Known mafia team: {mafia.known_mafia}")
    print("-" * 60)
    
    try:
        action = agent.get_night_action(context)
        print(f"\n✓ Action generated:")
        print(f"  Type: {action.get('type')}")
        print(f"  Target: {action.get('target')}")
        print("\n" + "-" * 60)
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vote_choice():
    """Test vote choice."""
    print("\n" + "=" * 60)
    print("TEST 4: Vote Choice")
    print("=" * 60)
    
    config = load_config("configs/simple_llm_agent.yaml")
    game_state = GameState(random_seed=42)
    judge = Judge(game_state, config)
    
    # Set up some nominations
    game_state.start_day()
    game_state.nominations[game_state.day_number] = [2, 5, 7]
    game_state.start_voting()
    
    player = game_state.players[0]
    agent = SimpleLLMAgent(player, config)
    
    context = agent.build_context(game_state)
    
    print(f"\nPlayer {player.player_number} choosing vote...")
    print(f"Nominated players: {game_state.nominations[game_state.day_number]}")
    print("-" * 60)
    
    try:
        vote = agent.get_vote_choice(context)
        print(f"\n✓ Vote choice: Player {vote}")
        print(f"  Is in nominations: {vote in game_state.nominations[game_state.day_number]}")
        print("\n" + "-" * 60)
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_speeches():
    """Test multiple players generating speeches to see variety."""
    print("\n" + "=" * 60)
    print("TEST 5: Multiple Players - Speech Variety")
    print("=" * 60)
    
    config = load_config("configs/simple_llm_agent.yaml")
    game_state = GameState(random_seed=42)
    judge = Judge(game_state, config)
    
    game_state.start_day()
    
    # Test first 3 players
    for i, player in enumerate(game_state.players[:3]):
        agent = SimpleLLMAgent(player, config)
        context = agent.build_context(game_state)
        
        print(f"\n--- Player {player.player_number} ({player.role.role_type.value}) ---")
        print("-" * 60)
        
        try:
            speech = agent.get_day_speech(context)
            # Show first 200 chars
            preview = speech[:200] + "..." if len(speech) > 200 else speech
            print(preview)
            print(f"\n[Length: {len(speech)} chars]")
        except Exception as e:
            print(f"❌ Error: {e}")
            break
        
        print()
    
    print("-" * 60)
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM Agent Output Examples")
    print("=" * 60)
    print("\nThis script tests LLM agent outputs in isolation.")
    print("It will show real responses from the OpenAI API.\n")
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not set!")
        return 1
    
    print(f"✓ API key found\n")
    
    tests = [
        ("Speech Generation", test_speech_generation),
        ("Sheriff Check", test_night_action_sheriff),
        ("Mafia Kill Claim", test_night_action_mafia),
        ("Vote Choice", test_vote_choice),
        ("Multiple Speeches", test_multiple_speeches),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
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

