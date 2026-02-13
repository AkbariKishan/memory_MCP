import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv, find_dotenv

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        # Load .env file if it exists
        load_dotenv(find_dotenv())
        
        self.config_path = config_path
        self.data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            # Try absolute path relative to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            abs_path = os.path.join(base_dir, self.config_path)
            if os.path.exists(abs_path):
                with open(abs_path, 'r') as f:
                    return yaml.safe_load(f)
            return {}
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        # Support nested keys like "monitor.model"
        keys = key.split('.')
        value = self.data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @property
    def google_api_key(self) -> str:
        # Check env var first, then config
        return os.environ.get("GOOGLE_API_KEY") or self.get("google.api_key")

# Global config instance
config = Config()
