"""
Project Service - Manages project-related business logic
"""
import os
from typing import List, Optional, Dict, Any

from core.config_manager import ConfigManager
from core.git_helper import GitHelper
from core.version_parser import detect_project_type, get_parser, VersionParser


class ProjectService:
    """
    Service for managing projects.
    Encapsulates project CRUD operations, status checking, and Git operations.
    """
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def get_all_projects(self) -> List[dict]:
        """Get all configured projects."""
        return self.config.get_projects()
    
    def add_project(self, project_data: dict) -> bool:
        """
        Add a new project.
        
        Args:
            project_data: Dict with 'path', 'type', 'publish_to', etc.
            
        Returns:
            True if added successfully, False if project already exists.
        """
        return self.config.add_project(project_data)
    
    def update_project(self, path: str, project_data: dict) -> bool:
        """
        Update an existing project's configuration.
        
        Args:
            path: The project path (identifier)
            project_data: New project data
            
        Returns:
            True if updated successfully.
        """
        return self.config.update_project(path, project_data)
    
    def remove_project(self, path: str) -> bool:
        """
        Remove a project from configuration.
        Does not delete actual files.
        
        Args:
            path: The project path to remove
            
        Returns:
            True if removed successfully.
        """
        return self.config.remove_project(path)
    
    def detect_project_type(self, path: str) -> Optional[str]:
        """
        Auto-detect project type based on files present.
        
        Args:
            path: Path to the project directory
            
        Returns:
            Detected project type string or None.
        """
        return detect_project_type(path)
    
    def get_project_status(self, project: dict) -> Dict[str, Any]:
        """
        Get comprehensive status for a project.
        
        Args:
            project: Project data dictionary
            
        Returns:
            Dict containing:
                - has_changes: bool
                - changed_files: list
                - ahead: int
                - behind: int
                - local_version: tuple or None
                - is_git_repo: bool
                - remotes: list
        """
        path = project.get("path", "")
        project_type = project.get("type", "")
        
        result = {
            "has_changes": False,
            "changed_files": [],
            "ahead": 0,
            "behind": 0,
            "local_version": None,
            "is_git_repo": False,
            "remotes": []
        }
        
        if not os.path.exists(path):
            result["error"] = "Path does not exist"
            return result
        
        git = GitHelper(path)
        result["is_git_repo"] = git.is_git_repo()
        
        if not result["is_git_repo"]:
            return result
        
        # Git status
        result["has_changes"] = git.has_local_changes()
        if result["has_changes"]:
            result["changed_files"] = git.get_changed_files()
        
        result["ahead"], result["behind"] = git.is_ahead_of_remote()
        result["remotes"] = git.get_remotes_with_details()
        
        # Version info
        parser = get_parser(project_type, project_path=path)
        if parser:
            version_file = os.path.join(path, parser.get_version_file())
            if os.path.exists(version_file):
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    result["local_version"] = parser.get_version(content)
                except Exception:
                    pass
        
        return result
    
    def get_quick_status(self, project: dict) -> str:
        """
        Get a quick status string for list display.
        
        Returns one of: 'synced', 'modified', 'ahead', 'behind', 'missing', 'not_git', 'unknown'
        """
        path = project.get("path", "")
        
        if not os.path.exists(path):
            return "missing"
        
        git = GitHelper(path)
        if not git.is_git_repo():
            return "not_git"
        
        has_changes = git.has_local_changes()
        ahead, behind = git.is_ahead_of_remote()
        
        if has_changes:
            return "modified"
        elif ahead > 0:
            return "ahead"
        elif behind > 0:
            return "behind"
        else:
            return "synced"
    
    def open_in_explorer(self, path: str) -> bool:
        """Open project folder in file explorer."""
        if os.path.exists(path):
            os.startfile(path)
            return True
        return False
    
    def open_in_vscode(self, path: str) -> bool:
        """Open project in VS Code."""
        git = GitHelper(path)
        return git.open_in_vscode()
