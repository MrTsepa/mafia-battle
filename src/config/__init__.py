"""Game configuration module."""

from .game_config import GameConfig, default_config
from .config_loader import load_config, load_config_from_yaml

__all__ = ['GameConfig', 'default_config', 'load_config', 'load_config_from_yaml']

