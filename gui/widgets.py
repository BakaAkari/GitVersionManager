"""
Git Version Manager - Custom Widgets
Custom QListWidgetItem and other UI components
"""
import os
import datetime
from PyQt5.QtWidgets import QListWidgetItem

from gui.icon_utils import IconUtils


class ProjectItem(QListWidgetItem):
    """Custom list item for projects."""
    
    STATUS_ICONS = {
        "synced": "✅",
        "modified": "⚠️",
        "ahead": "⬆️",
        "behind": "⬇️",
        "conflict": "❌",
        "checking": "🔄",
        "missing": "❓",
        "not_git": "📁",
        "unknown": "❓"
    }
    
    def __init__(self, project_data: dict):
        super().__init__()
        self.project_data = project_data
        self.status = "unknown"
        self.local_version = ""
        # Cached detailed status info
        self.cached_status = {
            "has_changes": False,
            "ahead": 0,
            "behind": 0,
            "platform_status": {},
            "last_check": None
        }
        self.update_display()
    
    def update_display(self):
        name = os.path.basename(self.project_data.get("path", "Unknown"))
        version_str = f" v{self.local_version}" if self.local_version else ""
        
        # Use proper icon
        self.setIcon(IconUtils.get_status_icon(self.status))
        self.setText(f"{name}{version_str}")
    
    def set_status(self, status: str, local_version: str = None):
        self.status = status
        if local_version is not None:
            self.local_version = local_version
        self.update_display()
    
    def set_cached_status(self, platform_status: dict, has_changes: bool, ahead: int, behind: int, changed_files: list = None):
        """Store cached detailed status info."""
        self.cached_status = {
            "has_changes": has_changes,
            "changed_files": changed_files or [],
            "ahead": ahead,
            "behind": behind,
            "platform_status": platform_status,
            "last_check": datetime.datetime.now()
        }
