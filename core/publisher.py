"""
Publisher - Upload releases to GitHub, Gitee, and Gitea
"""
import os
import requests
from typing import Optional, Dict, List
from urllib.parse import urlparse


class ReleasePublisher:
    """Base class for release publishers."""
    
    def __init__(self, token: str):
        self.token = token
    
    def publish(self, repo: str, tag: str, name: str, body: str, asset_path: str) -> dict:
        """Publish a release with an asset. Override in subclasses."""
        raise NotImplementedError


class GitHubPublisher(ReleasePublisher):
    """Publish releases to GitHub."""
    
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
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        return []
    
    def get_release_by_tag(self, repo: str, tag: str) -> Optional[dict]:
        """Get a release by tag name."""
        url = f"{self.API_BASE}/repos/{repo}/releases/tags/{tag}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
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
        response = requests.post(url, headers=self.headers, json=data)
        if response.status_code == 201:
            return response.json()
        print(f"GitHub create release failed: {response.status_code} - {response.text}")
        return None
    
    def upload_asset(self, upload_url: str, asset_path: str) -> Optional[dict]:
        """Upload an asset to a release."""
        # Remove the template part from upload_url
        upload_url = upload_url.split('{')[0]
        
        filename = os.path.basename(asset_path)
        url = f"{upload_url}?name={filename}"
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/zip"
        
        with open(asset_path, 'rb') as f:
            response = requests.post(url, headers=headers, data=f)
        
        if response.status_code == 201:
            return response.json()
        print(f"GitHub upload asset failed: {response.status_code} - {response.text}")
        return None
    
    def publish(self, repo: str, tag: str, name: str, body: str, asset_path: str) -> dict:
        """Create a release and upload the asset."""
        result = {"success": False, "platform": "github", "repo": repo}
        
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
        
        return result


class GiteePublisher(ReleasePublisher):
    """Publish releases to Gitee."""
    
    API_BASE = "https://gitee.com/api/v5"
    
    def __init__(self, token: str):
        super().__init__(token)
    
    def get_releases(self, repo: str) -> List[dict]:
        """Get list of releases for a repository."""
        url = f"{self.API_BASE}/repos/{repo}/releases"
        params = {"access_token": self.token}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
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
        response = requests.post(url, data=data)
        if response.status_code in [200, 201]:
            return response.json()
        print(f"Gitee create release failed: {response.status_code} - {response.text}")
        return None
    
    def upload_asset(self, release_id: int, repo: str, asset_path: str) -> Optional[dict]:
        """Upload an asset to a release."""
        # Note: Gitee API for asset upload is different and may require different handling
        # This is a simplified version
        url = f"{self.API_BASE}/repos/{repo}/releases/{release_id}/attach_files"
        
        filename = os.path.basename(asset_path)
        
        with open(asset_path, 'rb') as f:
            files = {'file': (filename, f, 'application/zip')}
            data = {"access_token": self.token}
            response = requests.post(url, data=data, files=files)
        
        if response.status_code in [200, 201]:
            return response.json()
        print(f"Gitee upload asset failed: {response.status_code} - {response.text}")
        return None
    
    def publish(self, repo: str, tag: str, name: str, body: str, asset_path: str) -> dict:
        """Create a release and upload the asset."""
        result = {"success": False, "platform": "gitee", "repo": repo}
        
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
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        return []
    
    def get_release_by_tag(self, repo: str, tag: str) -> Optional[dict]:
        """Get a release by tag name."""
        url = f"{self.base_url}/api/v1/repos/{repo}/releases/tags/{tag}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
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
        response = requests.post(url, headers=self.headers, json=data)
        if response.status_code in [200, 201]:
            return response.json()
        print(f"Gitea create release failed: {response.status_code} - {response.text}")
        return None
    
    def upload_asset(self, release_id: int, repo: str, asset_path: str) -> Optional[dict]:
        """Upload an asset to a release."""
        url = f"{self.base_url}/api/v1/repos/{repo}/releases/{release_id}/assets"
        
        filename = os.path.basename(asset_path)
        
        headers = {"Authorization": f"token {self.token}"}
        
        with open(asset_path, 'rb') as f:
            files = {'attachment': (filename, f, 'application/zip')}
            params = {"name": filename}
            response = requests.post(url, headers=headers, files=files, params=params)
        
        if response.status_code in [200, 201]:
            return response.json()
        print(f"Gitea upload asset failed: {response.status_code} - {response.text}")
        return None
    
    def publish(self, repo: str, tag: str, name: str, body: str, asset_path: str) -> dict:
        """Create a release and upload the asset."""
        result = {"success": False, "platform": "gitea", "repo": repo}
        
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
        
        return result


def get_publisher(platform: str, token: str, **kwargs) -> Optional[ReleasePublisher]:
    """Get the appropriate publisher for a platform."""
    if platform == "github":
        return GitHubPublisher(token)
    elif platform == "gitee":
        return GiteePublisher(token)
    elif platform == "gitea":
        base_url = kwargs.get("url", "")
        if base_url:
            return GiteaPublisher(token, base_url)
    return None
