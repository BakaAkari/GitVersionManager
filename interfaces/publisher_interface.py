"""
Publisher Interface - Abstract base for platform publishers
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type


class IPublisher(ABC):
    """
    Abstract interface for platform publishers.
    
    All publisher implementations must inherit from this interface
    and implement the required methods.
    
    Example:
        class MyPublisher(IPublisher):
            platform_name = "my_platform"
            
            def __init__(self, token: str, **kwargs):
                self.token = token
            
            def publish(self, repo, tag, name, body, asset_path) -> dict:
                # Implementation
                return {"success": True, "message": "Published"}
    """
    
    # Class attribute - must be defined by subclasses
    platform_name: str = ""
    
    @abstractmethod
    def __init__(self, token: str, **kwargs):
        """
        Initialize the publisher with authentication.
        
        Args:
            token: API token for authentication
            **kwargs: Platform-specific options (e.g., url for self-hosted)
        """
        pass
    
    @abstractmethod
    def publish(self, repo: str, tag: str, name: str, body: str, 
                asset_path: str = None) -> Dict[str, Any]:
        """
        Publish a release to the platform.
        
        Args:
            repo: Repository name in format "owner/repo"
            tag: Version tag (e.g., "v1.0.0")
            name: Release name/title
            body: Release description/notes
            asset_path: Optional path to asset file to upload
            
        Returns:
            Dict containing:
                - success: bool
                - message: str
                - url: str (optional, release URL)
                - asset_url: str (optional, uploaded asset URL)
        """
        pass
    
    def validate_config(self, repo: str, token: str) -> Dict[str, Any]:
        """
        Validate publisher configuration.
        
        Args:
            repo: Repository name
            token: API token
            
        Returns:
            Dict with 'valid' bool and 'errors' list.
        """
        errors = []
        
        if not repo:
            errors.append("仓库名称不能为空")
        elif "/" not in repo:
            errors.append("仓库格式应为: owner/repo")
        
        if not token:
            errors.append("API Token 不能为空")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def get_release_url(self, repo: str, tag: str) -> Optional[str]:
        """
        Get the expected URL for a release.
        Can be overridden by subclasses for platform-specific URLs.
        
        Returns:
            Expected release URL or None.
        """
        return None


class PublisherRegistry:
    """
    Registry for publisher implementations.
    
    Allows dynamic registration and lookup of publisher classes.
    
    Example:
        # Register a publisher
        PublisherRegistry.register(GitHubPublisher)
        
        # Get a publisher instance
        publisher = PublisherRegistry.get("github", token="xxx")
    """
    
    _publishers: Dict[str, Type[IPublisher]] = {}
    
    @classmethod
    def register(cls, publisher_class: Type[IPublisher]) -> None:
        """
        Register a publisher class.
        
        Args:
            publisher_class: Publisher class to register
            
        Raises:
            ValueError: If class has no platform_name
        """
        platform = getattr(publisher_class, 'platform_name', None)
        if not platform:
            raise ValueError(
                f"Publisher class {publisher_class.__name__} must define 'platform_name'"
            )
        cls._publishers[platform] = publisher_class
    
    @classmethod
    def unregister(cls, platform: str) -> bool:
        """
        Unregister a publisher.
        
        Returns:
            True if publisher was registered and removed.
        """
        if platform in cls._publishers:
            del cls._publishers[platform]
            return True
        return False
    
    @classmethod
    def get(cls, platform: str, token: str, **kwargs) -> Optional[IPublisher]:
        """
        Get a publisher instance for a platform.
        
        Args:
            platform: Platform name (e.g., "github", "gitee")
            token: API token
            **kwargs: Additional platform-specific options
            
        Returns:
            Publisher instance or None if not found.
        """
        publisher_class = cls._publishers.get(platform)
        if publisher_class:
            return publisher_class(token, **kwargs)
        return None
    
    @classmethod
    def get_available(cls) -> list:
        """
        Get list of registered platform names.
        """
        return list(cls._publishers.keys())
    
    @classmethod
    def is_registered(cls, platform: str) -> bool:
        """
        Check if a platform is registered.
        """
        return platform in cls._publishers
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered publishers.
        Mainly for testing purposes.
        """
        cls._publishers.clear()
