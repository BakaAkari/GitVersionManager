"""
Git Version Manager - Services Layer
Provides business logic services that decouple GUI from Core modules.
"""
from .project_service import ProjectService
from .version_service import VersionService
from .publish_service import PublishService

__all__ = ['ProjectService', 'VersionService', 'PublishService']
