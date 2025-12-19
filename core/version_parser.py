"""
Version Parser - Parse and modify version numbers in various project types
"""
import re
import ast
import os
from typing import Optional, Tuple, Dict
from abc import ABC, abstractmethod


class VersionParser(ABC):
    """Abstract base class for version parsers."""
    
    @abstractmethod
    def get_version(self, content: str) -> Optional[Tuple[int, int, int]]:
        """Parse version from file content."""
        pass
    
    @abstractmethod
    def set_version(self, content: str, version: Tuple[int, int, int]) -> str:
        """Update version in file content."""
        pass
    
    @abstractmethod
    def get_version_file(self) -> str:
        """Get the default version file name."""
        pass
    
    @staticmethod
    def bump_patch(version: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Increment patch version."""
        return (version[0], version[1], version[2] + 1)
    
    @staticmethod
    def bump_minor(version: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Increment minor version and reset patch."""
        return (version[0], version[1] + 1, 0)
    
    @staticmethod
    def bump_major(version: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Increment major version and reset minor and patch."""
        return (version[0] + 1, 0, 0)
    
    @staticmethod
    def version_to_string(version: Tuple[int, int, int]) -> str:
        """Convert version tuple to string."""
        return f"{version[0]}.{version[1]}.{version[2]}"


class BlenderAddonParser(VersionParser):
    """Parser for Blender addon bl_info."""
    
    VERSION_PATTERN = re.compile(r'"version"\s*:\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)')
    
    def get_version_file(self) -> str:
        return "__init__.py"
    
    def get_version(self, content: str) -> Optional[Tuple[int, int, int]]:
        match = self.VERSION_PATTERN.search(content)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return None
    
    def set_version(self, content: str, version: Tuple[int, int, int]) -> str:
        replacement = f'"version": ({version[0]}, {version[1]}, {version[2]})'
        return self.VERSION_PATTERN.sub(replacement, content)
    
    def get_addon_name(self, content: str) -> Optional[str]:
        """Extract addon name from bl_info."""
        match = re.search(r'"name"\s*:\s*"([^"]+)"', content)
        if match:
            return match.group(1)
        return None


class PackageJsonParser(VersionParser):
    """Parser for npm package.json."""
    
    VERSION_PATTERN = re.compile(r'"version"\s*:\s*"(\d+)\.(\d+)\.(\d+)"')
    
    def get_version_file(self) -> str:
        return "package.json"
    
    def get_version(self, content: str) -> Optional[Tuple[int, int, int]]:
        match = self.VERSION_PATTERN.search(content)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return None
    
    def set_version(self, content: str, version: Tuple[int, int, int]) -> str:
        replacement = f'"version": "{version[0]}.{version[1]}.{version[2]}"'
        return self.VERSION_PATTERN.sub(replacement, content)


class PyProjectParser(VersionParser):
    """Parser for Python pyproject.toml."""
    
    VERSION_PATTERN = re.compile(r'version\s*=\s*"(\d+)\.(\d+)\.(\d+)"')
    
    def get_version_file(self) -> str:
        return "pyproject.toml"
    
    def get_version(self, content: str) -> Optional[Tuple[int, int, int]]:
        match = self.VERSION_PATTERN.search(content)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return None
    
    def set_version(self, content: str, version: Tuple[int, int, int]) -> str:
        replacement = f'version = "{version[0]}.{version[1]}.{version[2]}"'
        return self.VERSION_PATTERN.sub(replacement, content)


class CustomParser(VersionParser):
    """Custom parser with user-defined pattern."""
    
    def __init__(self, version_file: str, pattern: str):
        self.version_file_name = version_file
        self.pattern = re.compile(pattern)
    
    def get_version_file(self) -> str:
        return self.version_file_name
    
    def get_version(self, content: str) -> Optional[Tuple[int, int, int]]:
        match = self.pattern.search(content)
        if match:
            groups = match.groups()
            if len(groups) >= 3:
                return (int(groups[0]), int(groups[1]), int(groups[2]))
        return None
    
    def set_version(self, content: str, version: Tuple[int, int, int]) -> str:
        # For custom patterns, we need to be careful about replacement
        # This is a simplified version that may need adjustment
        def replace_func(match):
            return match.group(0).replace(
                f"{match.group(1)}.{match.group(2)}.{match.group(3)}",
                f"{version[0]}.{version[1]}.{version[2]}"
            )
        return self.pattern.sub(replace_func, content)


class PythonAppParser(VersionParser):
    """
    Parser for Python compiled exe applications.
    
    Version file: version.py
    Format:
        __version__ = "1.0.0"
        VERSION = (1, 0, 0)  # optional tuple format
    """
    
    # Match __version__ = "x.y.z" or __version__ = 'x.y.z'
    VERSION_PATTERN = re.compile(r'__version__\s*=\s*["\'](\d+)\.(\d+)\.(\d+)["\']')
    # Match VERSION = (x, y, z)
    VERSION_TUPLE_PATTERN = re.compile(r'VERSION\s*=\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)')
    
    def get_version_file(self) -> str:
        return "version.py"
    
    def get_version(self, content: str) -> Optional[Tuple[int, int, int]]:
        # Try __version__ string first
        match = self.VERSION_PATTERN.search(content)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        
        # Try VERSION tuple
        match = self.VERSION_TUPLE_PATTERN.search(content)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        
        return None
    
    def set_version(self, content: str, version: Tuple[int, int, int]) -> str:
        # Update __version__ string
        content = self.VERSION_PATTERN.sub(
            f'__version__ = "{version[0]}.{version[1]}.{version[2]}"',
            content
        )
        
        # Update VERSION tuple if present
        content = self.VERSION_TUPLE_PATTERN.sub(
            f'VERSION = ({version[0]}, {version[1]}, {version[2]})',
            content
        )
        
        return content


def detect_project_type(project_path: str) -> Optional[str]:
    """Auto-detect project type based on files present."""
    # Check for Blender addon first
    if os.path.exists(os.path.join(project_path, "__init__.py")):
        init_path = os.path.join(project_path, "__init__.py")
        with open(init_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if 'bl_info' in content:
                return "blender_addon"
    
    # Check for Python App (has version.py and main.py or similar)
    if os.path.exists(os.path.join(project_path, "version.py")):
        # Check for typical Python app entry points
        has_entry = any(
            os.path.exists(os.path.join(project_path, f))
            for f in ["main.py", "app.py", "__main__.py"]
        )
        if has_entry:
            return "python_app"
    
    if os.path.exists(os.path.join(project_path, "package.json")):
        return "npm"
    
    if os.path.exists(os.path.join(project_path, "pyproject.toml")):
        return "python"
    
    if os.path.exists(os.path.join(project_path, "setup.py")):
        return "python_setup"
    
    return None


def get_parser(project_type: str, **kwargs) -> Optional[VersionParser]:
    """Get the appropriate parser for a project type."""
    parsers = {
        "blender_addon": BlenderAddonParser,
        "npm": PackageJsonParser,
        "python": PyProjectParser,
        "python_app": PythonAppParser,
    }
    
    if project_type == "custom":
        version_file = kwargs.get("version_file", "version.txt")
        pattern = kwargs.get("version_pattern", r"(\d+)\.(\d+)\.(\d+)")
        return CustomParser(version_file, pattern)
    
    parser_class = parsers.get(project_type)
    if parser_class:
        return parser_class()
    return None
