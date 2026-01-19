"""
Version Service - Manages version-related business logic
"""
import os
from typing import Optional, Tuple

from core.version_parser import get_parser, VersionParser


class VersionService:
    """
    Service for managing project versions.
    Encapsulates version reading, writing, and bumping operations.
    """
    
    def get_version_info(self, project_path: str, project_type: str) -> dict:
        """
        Get version information for a project.
        
        Args:
            project_path: Path to the project
            project_type: Type of project (blender_addon, npm, etc.)
            
        Returns:
            Dict containing:
                - version: tuple (major, minor, patch) or None
                - version_string: str or None
                - file_path: str
                - exists: bool
                - can_parse: bool
        """
        result = {
            "version": None,
            "version_string": None,
            "file_path": None,
            "exists": False,
            "can_parse": False
        }
        
        parser = get_parser(project_type, project_path=project_path)
        if not parser:
            return result
        
        version_file = os.path.join(project_path, parser.get_version_file())
        result["file_path"] = version_file
        result["exists"] = os.path.exists(version_file)
        
        if result["exists"]:
            try:
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                version = parser.get_version(content)
                if version:
                    result["version"] = version
                    result["version_string"] = VersionParser.version_to_string(version)
                    result["can_parse"] = True
            except Exception:
                pass
        
        return result
    
    def get_version(self, project_path: str, project_type: str) -> Optional[Tuple[int, int, int]]:
        """
        Get the current version tuple for a project.
        
        Returns:
            Version tuple (major, minor, patch) or None.
        """
        info = self.get_version_info(project_path, project_type)
        return info.get("version")
    
    def get_version_string(self, project_path: str, project_type: str) -> str:
        """
        Get the current version as a string.
        
        Returns:
            Version string like "1.2.3" or "0.0.0" if not found.
        """
        info = self.get_version_info(project_path, project_type)
        return info.get("version_string") or "0.0.0"
    
    def bump_version(self, project_path: str, project_type: str, 
                     bump_type: str = "patch") -> dict:
        """
        Bump the version number.
        
        Args:
            project_path: Path to the project
            project_type: Type of project
            bump_type: One of 'patch', 'minor', 'major'
            
        Returns:
            Dict containing:
                - success: bool
                - old_version: str
                - new_version: str
                - message: str
        """
        result = {
            "success": False,
            "old_version": None,
            "new_version": None,
            "message": ""
        }
        
        parser = get_parser(project_type, project_path=project_path)
        if not parser:
            result["message"] = "无法获取版本解析器"
            return result
        
        version_file = os.path.join(project_path, parser.get_version_file())
        
        # Create version file if it doesn't exist
        if not os.path.exists(version_file):
            try:
                initial_version = "0.0.1\n"
                with open(version_file, 'w', encoding='utf-8') as f:
                    f.write(initial_version)
                result["success"] = True
                result["old_version"] = None
                result["new_version"] = "0.0.1"
                result["message"] = f"创建版本文件: {version_file}"
                return result
            except Exception as e:
                result["message"] = f"创建版本文件失败: {e}"
                return result
        
        # Read current version
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            result["message"] = f"读取版本文件失败: {e}"
            return result
        
        current_version = parser.get_version(content)
        if not current_version:
            result["message"] = "无法解析当前版本"
            return result
        
        result["old_version"] = VersionParser.version_to_string(current_version)
        
        # Bump version
        if bump_type == "major":
            new_version = VersionParser.bump_major(current_version)
        elif bump_type == "minor":
            new_version = VersionParser.bump_minor(current_version)
        else:
            new_version = VersionParser.bump_patch(current_version)
        
        # Write new version
        try:
            new_content = parser.set_version(content, new_version)
            with open(version_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            result["success"] = True
            result["new_version"] = VersionParser.version_to_string(new_version)
            result["message"] = f"版本已更新: {result['old_version']} → {result['new_version']}"
        except Exception as e:
            result["message"] = f"写入版本文件失败: {e}"
        
        return result
    
    def create_version_file(self, project_path: str, project_type: str,
                           initial_version: str = "0.0.1") -> dict:
        """
        Create a new version file with initial version.
        
        Returns:
            Dict with success status and message.
        """
        result = {"success": False, "message": "", "file_path": None}
        
        parser = get_parser(project_type, project_path=project_path)
        if not parser:
            result["message"] = "无法获取版本解析器"
            return result
        
        version_file = os.path.join(project_path, parser.get_version_file())
        result["file_path"] = version_file
        
        if os.path.exists(version_file):
            result["message"] = "版本文件已存在"
            return result
        
        try:
            with open(version_file, 'w', encoding='utf-8') as f:
                f.write(f"{initial_version}\n")
            result["success"] = True
            result["message"] = f"创建版本文件成功: {version_file}"
        except Exception as e:
            result["message"] = f"创建失败: {e}"
        
        return result
    
    #
    # Utility methods
    #
    
    @staticmethod
    def version_to_string(version: Tuple[int, int, int]) -> str:
        """
        Convert version tuple to string.
        
        Args:
            version: Tuple of (major, minor, patch)
            
        Returns:
            Version string like "1.2.3"
        """
        return VersionParser.version_to_string(version)
    
    def parse_version_from_content(self, content: str, project_type: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse version from file content.
        
        Args:
            content: File content containing version
            project_type: Type of project to determine parser
            
        Returns:
            Version tuple or None if parsing fails.
        """
        parser = get_parser(project_type)
        if parser:
            return parser.get_version(content)
        return None
