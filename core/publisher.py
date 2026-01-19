"""
Publisher - Upload releases to GitHub, Gitee, and Gitea

Implements IPublisher interface for extensibility.
"""
import os
import requests
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse

# Import interface (with fallback for backwards compatibility)
try:
    from interfaces.publisher_interface import IPublisher, PublisherRegistry
    HAS_INTERFACE = True
except ImportError:
    HAS_INTERFACE = False
    IPublisher = object  # Fallback


class ReleasePublisher:
    """Base class for release publishers."""
    
    # Platform name for registry
    platform_name: str = ""
    
    def __init__(self, token: str, **kwargs):
        self.token = token
    
    def publish(self, repo: str, tag: str, name: str, body: str, asset_path: str = None) -> Dict[str, Any]:
        """Publish a release with an asset. Override in subclasses."""
        raise NotImplementedError


class GitHubPublisher(ReleasePublisher):
    """Publish releases to GitHub."""
    
    platform_name = "github"
    API_BASE = "https://api.github.com"
    
    def __init__(self, token: str):
        super().__init__(token)
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def get_releases(self, repo: str) -> List[dict]:
        """Get list of releases for a repository."""
        url = f"{self.API_BASE}/repos/{repo}/releases"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"GitHub get_releases network error: {e}")
        return []
    
    def get_release_by_tag(self, repo: str, tag: str) -> Optional[dict]:
        """Get a release by tag name."""
        url = f"{self.API_BASE}/repos/{repo}/releases/tags/{tag}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"GitHub get_release_by_tag network error: {e}")
        return None
    
    def create_release(self, repo: str, tag: str, name: str, body: str, draft: bool = False, prerelease: bool = False) -> Optional[dict]:
        """Create a new release."""
        url = f"{self.API_BASE}/repos/{repo}/releases"
        data = {
            "tag_name": tag,
            "name": name,
            "body": body,
            "draft": draft,
            "prerelease": prerelease
        }
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            if response.status_code == 201:
                return response.json()
            print(f"GitHub create release failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"GitHub create_release network error: {e}")
        return None
    
    def upload_asset(self, upload_url: str, asset_path: str) -> Optional[dict]:
        """Upload an asset to a release."""
        # Remove the template part from upload_url
        upload_url = upload_url.split('{')[0]
        
        filename = os.path.basename(asset_path)
        url = f"{upload_url}?name={filename}"
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/zip"
        
        try:
            with open(asset_path, 'rb') as f:
                response = requests.post(url, headers=headers, data=f, timeout=120)
            
            if response.status_code == 201:
                return response.json()
            print(f"GitHub upload asset failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"GitHub upload_asset network error: {e}")
        except IOError as e:
            print(f"GitHub upload_asset file error: {e}")
        return None
    
    def publish(self, repo: str, tag: str, name: str, body: str, asset_path: str) -> dict:
        """Create a release and upload the asset."""
        result = {"success": False, "platform": "github", "repo": repo}
        
        try:
            # Check if release already exists
            existing = self.get_release_by_tag(repo, tag)
            if existing:
                result["message"] = f"Release {tag} already exists"
                result["url"] = existing.get("html_url")
                return result
            
            # Create release
            release = self.create_release(repo, tag, name, body)
            if not release:
                result["message"] = "Failed to create release"
                return result
            
            # Upload asset
            upload_url = release.get("upload_url")
            if upload_url and asset_path:
                asset = self.upload_asset(upload_url, asset_path)
                if asset:
                    result["success"] = True
                    result["message"] = "Release published successfully"
                    result["url"] = release.get("html_url")
                else:
                    result["message"] = "Release created but asset upload failed"
                    result["url"] = release.get("html_url")
            else:
                result["success"] = True
                result["message"] = "Release created (no asset)"
                result["url"] = release.get("html_url")
        except Exception as e:
            result["message"] = f"Unexpected error: {e}"
        
        return result


class GiteePublisher(ReleasePublisher):
    """Publish releases to Gitee."""
    
    platform_name = "gitee"
    API_BASE = "https://gitee.com/api/v5"
    
    def __init__(self, token: str):
        super().__init__(token)
    
    def get_releases(self, repo: str) -> List[dict]:
        """Get list of releases for a repository."""
        url = f"{self.API_BASE}/repos/{repo}/releases"
        params = {"access_token": self.token}
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Gitee get_releases network error: {e}")
        return []
    
    def get_release_by_tag(self, repo: str, tag: str) -> Optional[dict]:
        """Get a release by tag name."""
        releases = self.get_releases(repo)
        for release in releases:
            if release.get("tag_name") == tag:
                return release
        return None
    
    def create_release(self, repo: str, tag: str, name: str, body: str) -> Optional[dict]:
        """Create a new release."""
        url = f"{self.API_BASE}/repos/{repo}/releases"
        data = {
            "access_token": self.token,
            "tag_name": tag,
            "name": name,
            "body": body,
            "target_commitish": "master"
        }
        try:
            response = requests.post(url, data=data, timeout=30)
            if response.status_code in [200, 201]:
                return response.json()
            print(f"Gitee create release failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Gitee create_release network error: {e}")
        return None
    
    def upload_asset(self, release_id: int, repo: str, asset_path: str) -> Optional[dict]:
        """Upload an asset to a release."""
        # Note: Gitee API for asset upload is different and may require different handling
        url = f"{self.API_BASE}/repos/{repo}/releases/{release_id}/attach_files"
        
        filename = os.path.basename(asset_path)
        
        try:
            with open(asset_path, 'rb') as f:
                files = {'file': (filename, f, 'application/zip')}
                data = {"access_token": self.token}
                response = requests.post(url, data=data, files=files, timeout=120)
            
            if response.status_code in [200, 201]:
                return response.json()
            print(f"Gitee upload asset failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Gitee upload_asset network error: {e}")
        except IOError as e:
            print(f"Gitee upload_asset file error: {e}")
        return None
    
    def publish(self, repo: str, tag: str, name: str, body: str, asset_path: str) -> dict:
        """Create a release and upload the asset."""
        result = {"success": False, "platform": "gitee", "repo": repo}
        
        try:
            # Check if release already exists
            existing = self.get_release_by_tag(repo, tag)
            if existing:
                result["message"] = f"Release {tag} already exists"
                return result
            
            # Create release
            release = self.create_release(repo, tag, name, body)
            if not release:
                result["message"] = "Failed to create release"
                return result
            
            # Upload asset
            release_id = release.get("id")
            if release_id and asset_path:
                asset = self.upload_asset(release_id, repo, asset_path)
                if asset:
                    result["success"] = True
                    result["message"] = "Release published successfully"
                else:
                    result["message"] = "Release created but asset upload failed"
            else:
                result["success"] = True
                result["message"] = "Release created (no asset)"
        except Exception as e:
            result["message"] = f"Unexpected error: {e}"
        
        return result


class GiteaPublisher(ReleasePublisher):
    """Publish releases to Gitea instance."""
    
    def __init__(self, token: str, base_url: str):
        super().__init__(token)
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json"
        }
    
    def get_releases(self, repo: str) -> List[dict]:
        """Get list of releases for a repository."""
        url = f"{self.base_url}/api/v1/repos/{repo}/releases"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Gitea get_releases network error: {e}")
        return []
    
    def get_release_by_tag(self, repo: str, tag: str) -> Optional[dict]:
        """Get a release by tag name."""
        url = f"{self.base_url}/api/v1/repos/{repo}/releases/tags/{tag}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Gitea get_release_by_tag network error: {e}")
        return None
    
    def create_release(self, repo: str, tag: str, name: str, body: str) -> Optional[dict]:
        """Create a new release."""
        url = f"{self.base_url}/api/v1/repos/{repo}/releases"
        data = {
            "tag_name": tag,
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": False
        }
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            if response.status_code in [200, 201]:
                return response.json()
            print(f"Gitea create release failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Gitea create_release network error: {e}")
        return None
    
    def upload_asset(self, release_id: int, repo: str, asset_path: str) -> Optional[dict]:
        """Upload an asset to a release."""
        url = f"{self.base_url}/api/v1/repos/{repo}/releases/{release_id}/assets"
        
        filename = os.path.basename(asset_path)
        
        headers = {"Authorization": f"token {self.token}"}
        
        try:
            with open(asset_path, 'rb') as f:
                files = {'attachment': (filename, f, 'application/zip')}
                params = {"name": filename}
                response = requests.post(url, headers=headers, files=files, params=params, timeout=120)
            
            if response.status_code in [200, 201]:
                return response.json()
            print(f"Gitea upload asset failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Gitea upload_asset network error: {e}")
        except IOError as e:
            print(f"Gitea upload_asset file error: {e}")
        return None
    
    def publish(self, repo: str, tag: str, name: str, body: str, asset_path: str) -> dict:
        """Create a release and upload the asset."""
        result = {"success": False, "platform": "gitea", "repo": repo}
        
        try:
            # Check if release already exists
            existing = self.get_release_by_tag(repo, tag)
            if existing:
                result["message"] = f"Release {tag} already exists"
                return result
            
            # Create release
            release = self.create_release(repo, tag, name, body)
            if not release:
                result["message"] = "Failed to create release"
                return result
            
            # Upload asset
            release_id = release.get("id")
            if release_id and asset_path:
                asset = self.upload_asset(release_id, repo, asset_path)
                if asset:
                    result["success"] = True
                    result["message"] = "Release published successfully"
                else:
                    result["message"] = "Release created but asset upload failed"
            else:
                result["success"] = True
                result["message"] = "Release created (no asset)"
        except Exception as e:
            result["message"] = f"Unexpected error: {e}"
        
        return result


def get_publisher(platform: str, token: str, **kwargs) -> Optional[ReleasePublisher]:
    """
    Get the appropriate publisher for a platform.
    
    First checks PublisherRegistry (if available), then falls back to
    built-in publishers for backwards compatibility.
    """
    # Try registry first
    if HAS_INTERFACE and PublisherRegistry.is_registered(platform):
        return PublisherRegistry.get(platform, token, **kwargs)
    
    # Fallback to built-in publishers
    if platform == "github":
        return GitHubPublisher(token)
    elif platform == "gitee":
        return GiteePublisher(token)
    elif platform == "gitea":
        base_url = kwargs.get("url", "")
        if base_url:
            return GiteaPublisher(token, base_url)
    return None


# Register built-in publishers with registry
if HAS_INTERFACE:
    PublisherRegistry.register(GitHubPublisher)
    PublisherRegistry.register(GiteePublisher)
    # Note: GiteaPublisher requires url parameter, registered separately
