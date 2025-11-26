"""
Configuration loader for YAML-based game configurations.
"""

import yaml
from pathlib import Path
from typing import Optional

from .game_config import GameConfig, default_config


def load_config_from_yaml(config_path: str) -> GameConfig:
    """
    Load game configuration from a YAML file.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        GameConfig instance with values from YAML file
        
    Raises:
        FileNotFoundError: If the config file doesn't exist
        yaml.YAMLError: If the YAML file is invalid
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    if config_dict is None:
        return default_config
    
    # Create config from dict, using defaults for missing values
    config = GameConfig()
    
    # Update config with values from YAML
    for key, value in config_dict.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            # Warn about unknown keys but don't fail
            print(f"Warning: Unknown config key '{key}' in YAML file")
    
    return config


def load_config(config_path: Optional[str] = None) -> GameConfig:
    """
    Load configuration from YAML file or return default.
    
    Args:
        config_path: Optional path to YAML config file. If None, returns default config.
        
    Returns:
        GameConfig instance
    """
    if config_path is None:
        return default_config
    
    return load_config_from_yaml(config_path)

