"""
Config Manager - Handle configuration persistence
"""
import os
import json
from typing import Dict, List, Optional, Any


class ConfigManager:
    """Manage application configuration."""
    
    DEFAULT_CONFIG = {
        "archive_path": "",
        "tokens": {
            "github": "",
            "gitee": "",
            "gitea": {"url": "", "token": ""}
        },
        "projects": [],
        "settings": {
            "theme": "light",
            "language": "zh_CN",
            "auto_fetch": True,
            "confirm_before_publish": True
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = config_path
        else:
            # Default to user's home directory
            self.config_path = os.path.join(
                os.path.expanduser("~"),
                ".git_version_manager",
                "config.json"
            )
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self) -> bool:
        """Load configuration from file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._merge_config(loaded)
                return True
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
        return False
    
    def _merge_config(self, loaded: dict):
        """Merge loaded config with defaults."""
        for key, value in loaded.items():
            if key in self.config:
                if isinstance(value, dict) and isinstance(self.config[key], dict):
                    self.config[key].update(value)
                else:
                    self.config[key] = value
    
    def save(self) -> bool:
        """Save configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving config: {e}")
        return False
    
    # Archive path
    def get_archive_path(self) -> str:
        return self.config.get("archive_path", "")
    
    def set_archive_path(self, path: str):
        self.config["archive_path"] = path
        self.save()
    
    # Tokens
    def get_token(self, platform: str) -> str:
        tokens = self.config.get("tokens", {})
        if platform == "gitea":
            return tokens.get("gitea", {}).get("token", "")
        return tokens.get(platform, "")
    
    def get_gitea_url(self) -> str:
        return self.config.get("tokens", {}).get("gitea", {}).get("url", "")
    
    def set_token(self, platform: str, token: str, url: str = ""):
        if "tokens" not in self.config:
            self.config["tokens"] = {}
        
        if platform == "gitea":
            self.config["tokens"]["gitea"] = {"url": url, "token": token}
        else:
            self.config["tokens"][platform] = token
        self.save()
    
    # Projects
    def get_projects(self) -> List[dict]:
        return self.config.get("projects", [])
    
    def add_project(self, project: dict) -> bool:
        """Add a project to the configuration."""
        projects = self.config.get("projects", [])
        
        # Check if project with same path already exists
        for p in projects:
            if p.get("path") == project.get("path"):
                return False
        
        projects.append(project)
        self.config["projects"] = projects
        self.save()
        return True
    
    def update_project(self, path: str, updates: dict):
        """Update a project's configuration."""
        projects = self.config.get("projects", [])
        for i, p in enumerate(projects):
            if p.get("path") == path:
                projects[i].update(updates)
                self.config["projects"] = projects
                self.save()
                return True
        return False
    
    def remove_project(self, path: str) -> bool:
        """Remove a project from configuration."""
        projects = self.config.get("projects", [])
        self.config["projects"] = [p for p in projects if p.get("path") != path]
        self.save()
        return True
    
    def get_project(self, path: str) -> Optional[dict]:
        """Get a project by path."""
        for p in self.config.get("projects", []):
            if p.get("path") == path:
                return p
        return None
    
    # Settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.config.get("settings", {}).get(key, default)
    
    def set_setting(self, key: str, value: Any):
        if "settings" not in self.config:
            self.config["settings"] = {}
        self.config["settings"][key] = value
        self.save()


def create_example_config(path: str):
    """Create an example config file."""
    example = {
        "archive_path": "D:/Archives",
        "tokens": {
            "github": "ghp_your_token_here",
            "gitee": "your_gitee_token",
            "gitea": {"url": "https://gitea.example.com", "token": "your_token"}
        },
        "projects": [
            {
                "path": "D:/Code/MyAddon",
                "type": "blender_addon",
                "publish_to": ["github", "gitee"],
                "github_repo": "username/repo",
                "gitee_repo": "username/repo"
            }
        ],
        "settings": {
            "theme": "light",
            "language": "zh_CN",
            "auto_fetch": True,
            "confirm_before_publish": True
        }
    }
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(example, f, indent=2, ensure_ascii=False)
