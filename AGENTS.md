# Mafia Battle - Cursor Rules

## Python Environment

- Always use `.venv` virtual environment for running Python code
- Activate `.venv` before executing any Python commands
- When running Python scripts or tests, ensure `.venv` is activated first

## Code testing
- If making substaintial changes to code remember to rerun tests (`pytest tests/ -v`) to make sure everything works
- Update tests if needed

## Code Style

- Follow PEP 8 conventions
- Use type hints for function parameters and return types
- Use dataclasses where appropriate (as seen in the codebase)
- Use descriptive variable and function names

## Project Structure

- Follow existing module organization: `src/core/`, `src/agents/`, `src/phases/`, `src/config/`
- Keep test files in `tests/` directory matching source structure
- Maintain separation of concerns: core game logic, agent implementations, phase handlers, and configuration

## Testing

- Use pytest for all tests
- Follow existing test naming conventions (`test_*.py`)
- Place test files in `tests/` directory
- Use pytest fixtures defined in `tests/conftest.py` when available

## Imports

- Use relative imports within `src/` package (e.g., `from ..core import GameState`)
- Group imports in this order: standard library, third-party, local
- Keep imports organized and avoid circular dependencies

## Code Patterns

- Use enums for constants (GamePhase, RoleType, Team)
- Use dataclasses for data structures
- Follow existing patterns for game state management and phase handlers
- Maintain consistency with existing codebase patterns and conventions

## Running Games in Terminal

When running games in the terminal, **always use the lightweight model `gpt-5-nano`** to reduce API costs and improve response times:

```bash
# Always specify gpt-5-nano when running in terminal
python main.py --config configs/simple_llm_agent.yaml --model gpt-5-nano

# Or use the short form
python main.py -c configs/simple_llm_agent.yaml -m gpt-5-nano
```

**Important:**
- Use `gpt-5-nano` for terminal/interactive runs (faster, cheaper)
- Use `gpt-5-mini` or other models only for specific testing/analysis
- The `--model` argument overrides the config file setting
- This ensures consistent, cost-effective runs during development
- don't use expressions like `2>&1 | head -100` it stops terminal output from beeing streamed to cursore console

## Reproducible Runs with Seed

For reproducible game runs, **always specify a seed** using the `--seed` or `-s` parameter. This ensures:
- Same role assignments across runs
- Same random behavior for dummy agents
- Consistent game outcomes for testing and debugging

```bash
# Run with a specific seed for reproducibility
python main.py --config configs/simple_llm_agent.yaml --model gpt-5-nano --seed 42

# Or use the short form
python main.py -c configs/simple_llm_agent.yaml -m gpt-5-nano -s 42

# Combine all options
python main.py -c configs/mixed_agents.yaml -m gpt-5-nano -s 12345
```

**Important:**
- Always use `--seed` or `-s` when you need reproducible runs
- If no seed is provided, a random seed will be generated and displayed in the game summary
- The seed affects role assignment, dummy agent behavior, and other random game elements
- Use the same seed to reproduce the exact same game setup and behavior

