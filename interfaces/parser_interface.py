"""
Version Parser Interface - Abstract base for version parsers
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Type, List
import os


class IVersionParser(ABC):
    """
    Abstract interface for version parsers.
    
    Version parsers handle reading and writing version information
    for different project types (Blender addons, npm packages, etc.).
    
    Example:
        class MyParser(IVersionParser):
            project_type = "my_project"
            version_file = "version.txt"
            
            def get_version(self, content: str) -> Optional[Tuple[int, int, int]]:
                # Parse version from content
                return (1, 0, 0)
            
            def set_version(self, content: str, version: Tuple) -> str:
                # Update version in content
                return content
    """
    
    # Class attributes - must be defined by subclasses
    project_type: str = ""
    version_file: str = ""
    
    def __init__(self, project_path: str = None):
        """
        Initialize the parser.
        
        Args:
            project_path: Optional path to the project directory
        """
        self.project_path = project_path
    
    @abstractmethod
    def get_version(self, content: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse version from file content.
        
        Args:
            content: Content of the version file
            
        Returns:
            Version tuple (major, minor, patch) or None if not found.
        """
        pass
    
    @abstractmethod
    def set_version(self, content: str, version: Tuple[int, int, int]) -> str:
        """
        Update version in file content.
        
        Args:
            content: Current file content
            version: New version tuple (major, minor, patch)
            
        Returns:
            Updated file content.
        """
        pass
    
    def get_version_file(self) -> str:
        """
        Get the version file path relative to project root.
        Can be overridden for dynamic file detection.
        
        Returns:
            Relative path to version file.
        """
        return self.version_file
    
    @classmethod
    def detect(cls, project_path: str) -> bool:
        """
        Detect if this parser is suitable for a given project.
        Default implementation checks for version_file existence.
        Can be overridden for custom detection logic.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if this parser should be used for the project.
        """
        if not cls.version_file:
            return False
        return os.path.exists(os.path.join(project_path, cls.version_file))


class ParserRegistry:
    """
    Registry for version parser implementations.
    
    Provides dynamic registration, lookup, and auto-detection
    of version parsers.
    
    Example:
        # Register parsers
        ParserRegistry.register(BlenderAddonParser)
        ParserRegistry.register(NpmParser)
        
        # Get parser by project type
        parser = ParserRegistry.get("blender_addon", "/path/to/project")
        
        # Auto-detect parser
        parser = ParserRegistry.detect("/path/to/project")
    """
    
    _parsers: Dict[str, Type[IVersionParser]] = {}
    _detection_order: List[str] = []
    
    @classmethod
    def register(cls, parser_class: Type[IVersionParser], 
                 priority: int = 100) -> None:
        """
        Register a parser class.
        
        Args:
            parser_class: Parser class to register
            priority: Detection priority (lower = higher priority)
            
        Raises:
            ValueError: If class has no project_type
        """
        project_type = getattr(parser_class, 'project_type', None)
        if not project_type:
            raise ValueError(
                f"Parser class {parser_class.__name__} must define 'project_type'"
            )
        
        cls._parsers[project_type] = parser_class
        
        # Update detection order based on priority
        if project_type not in cls._detection_order:
            cls._detection_order.append(project_type)
    
    @classmethod
    def unregister(cls, project_type: str) -> bool:
        """
        Unregister a parser.
        
        Returns:
            True if parser was registered and removed.
        """
        if project_type in cls._parsers:
            del cls._parsers[project_type]
            if project_type in cls._detection_order:
                cls._detection_order.remove(project_type)
            return True
        return False
    
    @classmethod
    def get(cls, project_type: str, project_path: str = None) -> Optional[IVersionParser]:
        """
        Get a parser instance by project type.
        
        Args:
            project_type: Type of project
            project_path: Optional path to project
            
        Returns:
            Parser instance or None if not found.
        """
        parser_class = cls._parsers.get(project_type)
        if parser_class:
            return parser_class(project_path)
        return None
    
    @classmethod
    def detect(cls, project_path: str) -> Optional[IVersionParser]:
        """
        Auto-detect the appropriate parser for a project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            Parser instance or None if no suitable parser found.
        """
        for project_type in cls._detection_order:
            parser_class = cls._parsers.get(project_type)
            if parser_class and parser_class.detect(project_path):
                return parser_class(project_path)
        return None
    
    @classmethod
    def get_available(cls) -> list:
        """
        Get list of registered project types.
        """
        return list(cls._parsers.keys())
    
    @classmethod
    def is_registered(cls, project_type: str) -> bool:
        """
        Check if a project type is registered.
        """
        return project_type in cls._parsers
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered parsers.
        Mainly for testing purposes.
        """
        cls._parsers.clear()
        cls._detection_order.clear()


# Utility functions for version manipulation
class VersionUtils:
    """
    Utility functions for version manipulation.
    """
    
    @staticmethod
    def version_to_string(version: Tuple[int, int, int]) -> str:
        """Convert version tuple to string."""
        return f"{version[0]}.{version[1]}.{version[2]}"
    
    @staticmethod
    def string_to_version(version_str: str) -> Optional[Tuple[int, int, int]]:
        """
        Convert version string to tuple.
        
        Args:
            version_str: Version string like "1.2.3"
            
        Returns:
            Version tuple or None if invalid.
        """
        try:
            parts = version_str.strip().split('.')
            if len(parts) >= 3:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            pass
        return None
    
    @staticmethod
    def bump_major(version: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Bump major version (X.0.0)."""
        return (version[0] + 1, 0, 0)
    
    @staticmethod
    def bump_minor(version: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Bump minor version (x.X.0)."""
        return (version[0], version[1] + 1, 0)
    
    @staticmethod
    def bump_patch(version: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Bump patch version (x.x.X)."""
        return (version[0], version[1], version[2] + 1)
    
    @staticmethod
    def compare(v1: Tuple[int, int, int], v2: Tuple[int, int, int]) -> int:
        """
        Compare two versions.
        
        Returns:
            -1 if v1 < v2
             0 if v1 == v2
             1 if v1 > v2
        """
        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
        return 0
