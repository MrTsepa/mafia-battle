# Test Suite

Comprehensive test suite for the Mafia game simulation with mocked LLM calls.

## Setup

Install test dependencies (creates the virtual environment automatically):
```bash
uv sync
```

## Running Tests

Run all tests:
```bash
uv run pytest tests/ -v
```

Run specific test file:
```bash
uv run pytest tests/test_game_engine.py -v
```

Run with coverage:
```bash
uv run pytest tests/ --cov=src --cov-report=html
```

## Test Structure

### `test_game_engine.py`
- Game initialization and setup
- Role distribution
- Mafia knowledge sharing
- Phase transitions
- Win condition detection
- Player elimination

### `test_judge.py`
- Nomination parsing and validation
- Speech validation (endings, length)
- Vote collection and counting
- Tie detection
- Default vote handling

### `test_day_phase.py`
- Speaking order management
- Speech processing
- Nomination handling
- First day vs subsequent day rules
- Auto-elimination on single nomination

### `test_voting.py`
- Vote collection
- Elimination from votes
- Tie-breaking procedure
- "Eliminate all" vote

### `test_night_phase.py`
- Mafia kill claims and Don's decision
- Don checks for Sheriff
- Sheriff checks for Mafia/Civilians
- First night rules (no checks)

### `test_full_game.py`
- Complete game flow integration
- Win scenarios
- Game state persistence

## Mocking Strategy

All LLM calls are mocked to ensure tests are lightweight and don't make real API calls:

### Automatic Mocking (conftest.py)
- **`_call_llm()`** - Automatically mocked for ALL tests via `autouse` fixture
  - This provides a safety layer to prevent any real API calls
  - Returns empty string by default (methods will be mocked anyway)

### Per-Test Mocking
Individual tests should mock the high-level methods:
- **`get_day_speech()`** - Returns mock speeches
- **`get_night_action()`** - Returns mock night actions  
- **`get_vote_choice()`** - Returns mock vote choices

### Why Both Layers?
1. **High-level method mocking** - Ensures tests have predictable, controlled behavior
2. **`_call_llm` mocking** - Safety net to prevent real API calls even if high-level mocking fails

This two-layer approach ensures:
- Tests are fast and lightweight (no network calls)
- Tests don't require API keys
- Tests are deterministic and reproducible
- No accidental API usage or costs

## Example Test Run

```bash
uv run pytest tests/test_game_engine.py -v

tests/test_game_engine.py::test_game_setup PASSED
tests/test_game_engine.py::test_role_distribution PASSED
tests/test_game_engine.py::test_mafia_knowledge PASSED
...
```

