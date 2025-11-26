"""
Exceptions for agent-related errors.
"""


class LLMEmptyResponseError(Exception):
    """Raised when LLM API call returns an empty response."""
    
    def __init__(self, player_number: int, action_type: str, message: str = ""):
        self.player_number = player_number
        self.action_type = action_type
        self.message = message or f"LLM returned empty response for Player {player_number} during {action_type}"
        super().__init__(self.message)

