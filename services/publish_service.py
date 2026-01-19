"""
Publish Service - Manages publishing and packaging business logic
"""
import os
from typing import List, Dict, Any, Optional

from core.config_manager import ConfigManager
from core.git_helper import GitHelper
from core.packager import Packager
from core.publisher import get_publisher
from core.version_parser import get_parser, VersionParser


class PublishService:
    """
    Service for managing project publishing workflow.
    Handles packaging, Git operations, and platform publishing.
    """
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def get_project_version(self, project: dict) -> str:
        """
        Get version string for a project.
        
        Returns:
            Version string like "1.2.3" or "0.0.0".
        """
        path = project.get("path", "")
        project_type = project.get("type", "")
        
        parser = get_parser(project_type, project_path=path)
        if not parser:
            return "0.0.0"
        
        version_file = os.path.join(path, parser.get_version_file())
        if not os.path.exists(version_file):
            return "0.0.0"
        
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                content = f.read()
            version = parser.get_version(content)
            if version:
                return VersionParser.version_to_string(version)
        except Exception:
            pass
        
        return "0.0.0"
    
    def package_project(self, project: dict, progress_callback=None) -> dict:
        """
        Package a project into a ZIP file.
        
        Args:
            project: Project data dictionary
            progress_callback: Optional callback(msg: str) for progress updates
            
        Returns:
            Dict containing:
                - success: bool
                - zip_path: str or None
                - message: str
        """
        result = {"success": False, "zip_path": None, "message": ""}
        
        path = project.get("path", "")
        project_name = os.path.basename(path)
        project_type = project.get("type", "")
        version = self.get_project_version(project)
        archive_path = self.config.get_archive_path() or os.path.dirname(path)
        
        if progress_callback:
            progress_callback(f"📦 开始打包 {project_name}...")
            progress_callback(f"  📂 输出目录: {archive_path}")
            progress_callback(f"  🏷️ 版本: {version}")
        
        try:
            packager = Packager(path, project_name, archive_path)
            
            if project_type == "python_app":
                # Package dist/ folder for compiled apps
                dist_path = os.path.join(path, "dist")
                if not os.path.exists(dist_path):
                    result["message"] = f"dist/ 文件夹不存在: {dist_path}"
                    return result
                
                if progress_callback:
                    progress_callback("📂 打包 dist/ 编译文件...")
                
                zip_path = packager.create_dist_zip(version)
            else:
                if progress_callback:
                    progress_callback("📂 收集源文件...")
                
                zip_path = packager.create_zip(version)
            
            if os.path.exists(zip_path):
                result["success"] = True
                result["zip_path"] = zip_path
                result["message"] = f"打包完成: {zip_path}"
                
                if progress_callback:
                    zip_size = os.path.getsize(zip_path) / (1024 * 1024)
                    progress_callback(f"  📦 文件大小: {zip_size:.2f} MB")
                    progress_callback(f"✅ 打包完成: {zip_path}")
            else:
                result["message"] = "ZIP 文件创建失败"
                
        except Exception as e:
            result["message"] = str(e)
            if progress_callback:
                progress_callback(f"❌ 打包失败: {e}")
        
        return result
    
    def get_zip_path(self, project: dict) -> Optional[str]:
        """
        Get the expected ZIP file path for a project.
        
        Returns:
            Full path to the ZIP file, or None if not found.
        """
        path = project.get("path", "")
        project_name = os.path.basename(path)
        version = self.get_project_version(project)
        archive_path = self.config.get_archive_path() or os.path.dirname(path)
        
        zip_filename = f"{project_name}_v{version}.zip"
        zip_path = os.path.join(archive_path, zip_filename)
        
        if os.path.exists(zip_path):
            return zip_path
        return None
    
    def commit_and_push_all(self, project: dict, message: str, 
                           progress_callback=None) -> dict:
        """
        Commit all changes and push to all remotes.
        
        Args:
            project: Project data dictionary
            message: Commit message
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict with success status and details.
        """
        result = {
            "success": False,
            "committed": False,
            "push_results": {},
            "message": ""
        }
        
        path = project.get("path", "")
        git = GitHelper(path)
        
        if not git.is_git_repo():
            result["message"] = "不是 Git 仓库"
            return result
        
        # Check for changes
        if not git.has_local_changes():
            result["message"] = "没有需要提交的修改"
            return result
        
        # Stage all changes
        if progress_callback:
            progress_callback("📦 暂存所有修改...")
        
        try:
            git._run_git(["add", "-A"])
        except Exception as e:
            result["message"] = f"暂存失败: {e}"
            return result
        
        # Commit
        if progress_callback:
            progress_callback(f"💾 提交修改: {message[:50]}...")
        
        if not git.commit(message):
            result["message"] = "提交失败"
            return result
        
        result["committed"] = True
        if progress_callback:
            progress_callback("✅ 提交成功")
        
        # Push to all remotes
        if progress_callback:
            progress_callback("📤 推送到所有远程仓库...")
        
        remotes = git.get_remotes()
        branch = git.get_current_branch() or "main"
        success_count = 0
        
        for remote in remotes:
            name = remote.get("name", "")
            if progress_callback:
                progress_callback(f"  → {name}...")
            
            if git.push(name, branch):
                result["push_results"][name] = True
                success_count += 1
                if progress_callback:
                    progress_callback(f"    ✅ 成功")
            else:
                result["push_results"][name] = False
                if progress_callback:
                    progress_callback(f"    ⚠️ 失败")
        
        result["success"] = success_count == len(remotes)
        result["message"] = f"提交并推送完成 {success_count}/{len(remotes)}"
        
        return result
    
    def publish_to_platforms(self, project: dict, zip_path: str,
                            progress_callback=None) -> Dict[str, dict]:
        """
        Publish project to configured platforms.
        
        Args:
            project: Project data dictionary
            zip_path: Path to the ZIP file to upload
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict mapping platform names to result dicts.
        """
        results = {}
        
        path = project.get("path", "")
        project_name = os.path.basename(path)
        version = self.get_project_version(project)
        publish_to = project.get("publish_to", [])
        tag = f"v{version}"
        
        # Push to all remotes first
        git = GitHelper(path)
        if git.is_git_repo():
            if progress_callback:
                progress_callback("📤 推送代码到所有远程仓库...")
            
            remotes = git.get_remotes_with_details()
            
            # Create tag
            if progress_callback:
                progress_callback(f"🏷️ 创建标签: {tag}")
            git.create_tag(tag, f"Release {tag}")
            
            # Push to each remote
            for remote in remotes:
                remote_name = remote.get("name", "")
                platform = remote.get("platform", "unknown")
                
                if remote_name:
                    if progress_callback:
                        progress_callback(f"  → 推送到 {platform} ({remote_name})...")
                    
                    branch = git.get_current_branch() or "main"
                    git.push(remote_name, branch)
                    git.push_tags(remote_name)
        
        # Publish releases
        if progress_callback:
            progress_callback("📦 发布 Release...")
        
        for platform in publish_to:
            token = self.config.get_token(platform)
            if not token:
                if progress_callback:
                    progress_callback(f"⚠️ {platform}: 未配置Token")
                results[platform] = {"success": False, "message": "未配置Token"}
                continue
            
            repo_key = f"{platform}_repo"
            repo = project.get(repo_key, "")
            if not repo:
                if progress_callback:
                    progress_callback(f"⚠️ {platform}: 未配置仓库")
                results[platform] = {"success": False, "message": "未配置仓库"}
                continue
            
            publisher = get_publisher(
                platform, token,
                url=self.config.get_gitea_url() if platform == "gitea" else ""
            )
            
            if publisher:
                if progress_callback:
                    progress_callback(f"🚀 发布到 {platform}: {repo}")
                
                result = publisher.publish(
                    repo=repo,
                    tag=tag,
                    name=f"{project_name} {tag}",
                    body=f"Release {tag}",
                    asset_path=zip_path
                )
                
                if result.get("success"):
                    if progress_callback:
                        progress_callback(f"✅ {platform}: {result.get('message')}")
                else:
                    if progress_callback:
                        progress_callback(f"❌ {platform}: {result.get('message')}")
                
                results[platform] = result
        
        if progress_callback:
            progress_callback("✅ 发布流程完成")
        
        return results
    
    def full_publish_workflow(self, project: dict, commit_message: str = None,
                             progress_callback=None) -> dict:
        """
        Execute the full publish workflow:
        1. Commit and push changes (if message provided)
        2. Package the project
        3. Publish to all platforms
        
        Returns:
            Dict with overall results.
        """
        result = {
            "success": False,
            "commit_result": None,
            "package_result": None,
            "publish_results": {},
            "message": ""
        }
        
        # Step 1: Commit and push (optional)
        if commit_message:
            if progress_callback:
                progress_callback("📝 步骤 1: 提交更改...")
            result["commit_result"] = self.commit_and_push_all(
                project, commit_message, progress_callback
            )
        
        # Step 2: Package
        if progress_callback:
            progress_callback("📦 步骤 2: 打包项目...")
        result["package_result"] = self.package_project(project, progress_callback)
        
        if not result["package_result"]["success"]:
            result["message"] = f"打包失败: {result['package_result']['message']}"
            return result
        
        zip_path = result["package_result"]["zip_path"]
        
        # Step 3: Publish
        if progress_callback:
            progress_callback("🚀 步骤 3: 发布到平台...")
        result["publish_results"] = self.publish_to_platforms(
            project, zip_path, progress_callback
        )
        
        # Check overall success
        success_count = sum(1 for r in result["publish_results"].values() if r.get("success"))
        total_count = len(result["publish_results"])
        
        result["success"] = success_count == total_count and total_count > 0
        result["message"] = f"发布完成: {success_count}/{total_count} 个平台成功"
        
        return result
