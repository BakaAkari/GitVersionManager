"""
Git Version Manager - Worker Threads
Background workers for long-running operations

Uses Services layer for business logic.
"""
import os
from PyQt5.QtCore import QThread, pyqtSignal

# Services layer for business logic
from services import ProjectService, VersionService, PublishService

# Core modules (for low-level operations not covered by services)
from core.git_helper import GitHelper
from core.packager import Packager
from core.publisher import get_publisher


class WorkerThread(QThread):
    """Worker thread for long-running operations."""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result or {})
        except Exception as e:
            self.error.emit(str(e))


class RefreshWorker(QThread):
    """Worker thread for refreshing project status."""
    progress = pyqtSignal(str)  # Log messages
    update_label = pyqtSignal(str, str, str)  # label_name, text, color
    finished = pyqtSignal(dict)  # Final result
    
    def __init__(self, project_path: str, project_type: str):
        super().__init__()
        self.project_path = project_path
        self.project_type = project_type
    
    def run(self):
        result = {
            "has_changes": False,
            "ahead": 0,
            "behind": 0,
            "local_version": None,
            "platform_status": {},
            "item_status": "unknown"
        }
        
        self.progress.emit(f"🔍 检查 Git 仓库...")
        git = GitHelper(self.project_path)
        
        if not git.is_git_repo():
            self.progress.emit("❌ 不是Git仓库")
            self.finished.emit(result)
            return
        
        # Get remotes
        self.progress.emit("📡 获取远程仓库列表...")
        remotes = git.get_remotes_with_details()
        self.progress.emit(f"  找到 {len(remotes)} 个远程仓库")
        
        # Fetch all remotes
        for remote in remotes:
            name = remote.get("name", "origin")
            platform = remote.get("platform", "unknown")
            self.progress.emit(f"⬇️ 正在获取 {platform} ({name})...")
            git.fetch(name)
        
        # Check local changes
        self.progress.emit("📂 检查本地修改...")
        result["has_changes"] = git.has_local_changes()
        if result["has_changes"]:
            result["changed_files"] = git.get_changed_files()
        else:
            result["changed_files"] = []
        
        # Local version using VersionService
        self.progress.emit("🏷️ 读取本地版本...")
        version_service = VersionService()
        version_info = version_service.get_version_info(self.project_path, self.project_type)
        
        if version_info.get("version"):
            local_version = version_info["version"]
            result["local_version"] = local_version
            local_version_str = version_service.version_to_string(local_version)
            self.progress.emit(f"  本地版本: {local_version_str}")
            self.update_label.emit("local_version", local_version_str, "#d0d0d0")
        
        # Per-platform remote versions  
        platform_status = {}
        version_file = version_info.get("file_path", "")
        version_filename = os.path.basename(version_file) if version_file else "__init__.py"
        
        for remote in remotes:
            remote_name = remote.get("name", "")
            platform = remote.get("platform", "")
            
            if not platform:
                continue
            
            # Skip if we already have a successful status for this platform
            if platform in platform_status and platform_status[platform][1] != "gray":
                self.progress.emit(f"  ⏭️ {platform} ({remote_name}) 已有成功结果，跳过")
                continue
            
            self.progress.emit(f"🔍 检查 {platform} ({remote_name}) 远程版本...")
            
            remote_content = git.get_remote_file_content(
                version_filename,
                remote=remote_name
            )
            
            if remote_content:
                # Use VersionService to parse remote version
                remote_version = version_service.parse_version_from_content(
                    remote_content, self.project_type
                )
                if remote_version:
                    version_str = version_service.version_to_string(remote_version)
                    local_version = result.get("local_version")
                    
                    if local_version:
                        if local_version > remote_version:
                            status = f"⬆️ {version_str} (本地较新)"
                            color = "green"
                        elif local_version < remote_version:
                            status = f"⬇️ {version_str} (远程较新)"
                            color = "orange"
                        else:
                            status = f"✅ {version_str} (已同步)"
                            color = "#d0d0d0"
                    else:
                        status = version_str
                        color = "#d0d0d0"
                    
                    platform_status[platform] = (status, color)
                    self.progress.emit(f"  ✅ {platform}: {status}")
                else:
                    self.progress.emit(f"  ⚠️ {platform} ({remote_name}): 无法解析版本")
                    if platform not in platform_status:
                        platform_status[platform] = ("无法解析", "gray")
            else:
                self.progress.emit(f"  ⚠️ {platform} ({remote_name}): 无法获取远程数据")
                if platform not in platform_status:
                    platform_status[platform] = ("无远程数据", "gray")
        
        result["platform_status"] = platform_status
        
        # Check ahead/behind
        self.progress.emit("📊 检查提交状态...")
        ahead, behind = git.is_ahead_of_remote()
        result["ahead"] = ahead
        result["behind"] = behind
        
        # Determine item status
        if result["has_changes"]:
            result["item_status"] = "modified"
        elif ahead > 0:
            result["item_status"] = "ahead"
        elif behind > 0:
            result["item_status"] = "behind"
        else:
            result["item_status"] = "synced"
        
        self.progress.emit("✅ 刷新完成")
        self.finished.emit(result)


class BuildWorker(QThread):
    """Worker thread for building project (compiling)."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, build_script: str):
        super().__init__()
        self.build_script = build_script
    
    def run(self):
        try:
            self.progress.emit(f"🔨 执行构建脚本: {os.path.basename(self.build_script)}...")
            import subprocess
            
            # Use Popen for real-time output
            process = subprocess.Popen(
                [self.build_script], 
                cwd=os.path.dirname(self.build_script),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='mbcs',
                errors='replace',
                shell=True,
                bufsize=1
            )
            
            # Stream output
            for line in process.stdout:
                self.progress.emit(f"  > {line.strip()}")
            
            process.wait()
            
            if process.returncode != 0:
                self.progress.emit(f"❌ 构建失败 (Code {process.returncode})")
                self.finished.emit(False, f"Build script failed with code {process.returncode}")
                return
            
            self.progress.emit("✅ 构建脚本执行成功")
            self.finished.emit(True, "构建成功")
        except Exception as e:
            self.progress.emit(f"❌ 构建失败: {e}")
            self.finished.emit(False, str(e))


class PackageWorker(QThread):
    """Worker thread for packaging project."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message/path
    
    def __init__(self, project_path: str, project_name: str, archive_path: str, version: str, project_type: str = None):
        super().__init__()
        self.project_path = project_path
        self.project_name = project_name
        self.archive_path = archive_path
        self.version = version
        self.project_type = project_type
    
    def run(self):
        self.progress.emit(f"📦 开始打包 {self.project_name}...")
        self.progress.emit(f"  📂 输出目录: {self.archive_path}")
        
        try:
            self.progress.emit("⏳ 打包正在进行中...")
            packager = Packager(self.project_path, self.project_name, self.archive_path)
            
            # Use dist packaging for python_app (compiled exe projects)
            if self.project_type == "python_app":
                self.progress.emit("📂 打包 dist/ 编译文件...")
                self.progress.emit(f"  📁 源路径: {self.project_path}")
                self.progress.emit(f"  📁 目标路径: {self.archive_path}")
                self.progress.emit(f"  🏷️ 版本: {self.version}")
                
                # Check if dist folder exists
                dist_path = os.path.join(self.project_path, "dist")
                if not os.path.exists(dist_path):
                    raise FileNotFoundError(f"❌ dist/ 文件夹不存在: {dist_path}\n请先执行编译项目！")
                
                # List dist contents
                dist_contents = os.listdir(dist_path)
                self.progress.emit(f"  📦 dist/ 内容: {', '.join(dist_contents) if dist_contents else '(空)'}")
                
                if not dist_contents:
                    raise FileNotFoundError(f"❌ dist/ 文件夹为空: {dist_path}\n请先执行编译项目！")
                
                zip_path = packager.create_dist_zip(self.version)
            else:
                self.progress.emit("📂 收集源文件...")
                self.progress.emit(f"  📁 源路径: {self.project_path}")
                self.progress.emit(f"  📁 目标路径: {self.archive_path}")
                self.progress.emit(f"  🏷️ 版本: {self.version}")
                zip_path = packager.create_zip(self.version)
            
            if not os.path.exists(zip_path):
                raise FileNotFoundError(f"❌ 无法创建 ZIP 文件: {zip_path}")
            
            # Get file size
            zip_size = os.path.getsize(zip_path)
            zip_size_mb = zip_size / (1024 * 1024)
            self.progress.emit(f"  📦 文件大小: {zip_size_mb:.2f} MB")
            self.progress.emit(f"✅ 打包完成: {zip_path}")
            self.finished.emit(True, zip_path)
        except Exception as e:
            self.progress.emit(f"❌ 打包失败: {e}")
            self.finished.emit(False, str(e))


class PublishWorker(QThread):
    """Worker thread for publishing to platforms."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)  # results per platform
    
    def __init__(self, project_path: str, project_name: str, version: str, 
                 zip_path: str, publish_to: list, project_data: dict, config):
        super().__init__()
        self.project_path = project_path
        self.project_name = project_name
        self.version = version
        self.zip_path = zip_path
        self.publish_to = publish_to
        self.project_data = project_data
        self.config = config
    
    def run(self):
        results = {}
        tag = f"v{self.version}"
        
        # Push to all remotes first
        git = GitHelper(self.project_path)
        if git.is_git_repo():
            self.progress.emit("📤 推送代码到所有远程仓库...")
            remotes = git.get_remotes_with_details()
            
            # Create tag if not exists
            self.progress.emit(f"🏷️ 创建标签: {tag}")
            git.create_tag(tag, f"Release {tag}")
            
            # Push to each remote
            for remote in remotes:
                remote_name = remote.get("name", "")
                platform = remote.get("platform", "unknown")
                
                if remote_name:
                    self.progress.emit(f"  → 推送到 {platform} ({remote_name})...")
                    
                    branch = git.get_current_branch() or "main"
                    if git.push(remote_name, branch):
                        self.progress.emit(f"    ✅ 分支推送成功")
                    else:
                        self.progress.emit(f"    ⚠️ 分支推送失败")
                    
                    if git.push_tags(remote_name):
                        self.progress.emit(f"    ✅ 标签推送成功")
                    else:
                        self.progress.emit(f"    ⚠️ 标签推送失败")
        
        # Publish releases
        self.progress.emit("📦 发布 Release...")
        for platform in self.publish_to:
            token = self.config.get_token(platform)
            if not token:
                self.progress.emit(f"⚠️ {platform}: 未配置Token")
                results[platform] = {"success": False, "message": "未配置Token"}
                continue
            
            repo_key = f"{platform}_repo"
            repo = self.project_data.get(repo_key, "")
            if not repo:
                self.progress.emit(f"⚠️ {platform}: 未配置仓库")
                results[platform] = {"success": False, "message": "未配置仓库"}
                continue
            
            publisher = get_publisher(
                platform, token,
                url=self.config.get_gitea_url() if platform == "gitea" else ""
            )
            
            if publisher:
                self.progress.emit(f"🚀 发布到 {platform}: {repo}")
                result = publisher.publish(
                    repo=repo,
                    tag=tag,
                    name=f"{self.project_name} {tag}",
                    body=f"Release {tag}",
                    asset_path=self.zip_path
                )
                
                if result.get("success"):
                    self.progress.emit(f"✅ {platform}: {result.get('message')}")
                else:
                    self.progress.emit(f"❌ {platform}: {result.get('message')}")
                results[platform] = result
        
        self.progress.emit("✅ 发布流程完成")
        self.finished.emit(results)


class ProjectStatusWorker(QThread):
    """Worker for checking a single project's status (used for parallel startup check)."""
    finished = pyqtSignal(str, str, str)  # path, status, local_version
    
    def __init__(self, project_data: dict):
        super().__init__()
        self.project_data = project_data
    
    def run(self):
        path = self.project_data.get("path", "")
        project_type = self.project_data.get("type", "")
        
        if not os.path.exists(path):
            self.finished.emit(path, "missing", "")
            return
        
        git = GitHelper(path)
        if not git.is_git_repo():
            self.finished.emit(path, "not_git", "")
            return
        
        # Get local version using VersionService
        local_version_str = ""
        version_service = VersionService()
        version_info = version_service.get_version_info(path, project_type)
        
        if version_info.get("version"):
            local_version_str = version_service.version_to_string(version_info["version"])
        
        # Check git status
        has_changes = git.has_local_changes()
        ahead, behind = git.is_ahead_of_remote()
        
        if has_changes:
            status = "modified"
        elif ahead > 0:
            status = "ahead"
        elif behind > 0:
            status = "behind"
        else:
            status = "synced"
        
        self.finished.emit(path, status, local_version_str)


class SyncStatusWorker(QThread):
    """Worker for checking sync status of all remotes."""
    progress = pyqtSignal(str)
    remote_found = pyqtSignal(dict)  # name, platform, ahead, behind, error
    finished = pyqtSignal()
    
    def __init__(self, project_path: str):
        super().__init__()
        self.project_path = project_path
    
    def run(self):
        git = GitHelper(self.project_path)
        
        self.progress.emit("🔍 获取远程仓库列表...")
        remotes = git.get_remotes_with_details()
        self.progress.emit(f"  找到 {len(remotes)} 个远程仓库")
        
        for remote in remotes:
            name = remote.get("name", "")
            platform = remote.get("platform", "unknown")
            
            self.progress.emit(f"📡 检查 {name} ({platform}) 状态...")
            status = git.get_remote_status(name)
            
            result = {
                "name": name,
                "platform": platform,
                "ahead": status.get("ahead", 0),
                "behind": status.get("behind", 0),
                "error": status.get("error")
            }
            self.remote_found.emit(result)
        
        # Check conflicts
        self.progress.emit("🔍 检查冲突状态...")
        has_conflicts = git.has_merge_conflicts()
        if has_conflicts:
            conflicts = git.get_conflict_files()
            self.progress.emit(f"⚠️ 检测到 {len(conflicts)} 个冲突文件")
        else:
            self.progress.emit("✅ 无冲突")
        
        self.progress.emit("✅ 状态检查完成")
        self.finished.emit()


class SyncOperationWorker(QThread):
    """Worker for async git sync operations."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, project_path: str, operation: str, remote: str = None, branch: str = None):
        super().__init__()
        self.project_path = project_path
        self.operation = operation
        self.remote = remote
        self.branch = branch
    
    def run(self):
        git = GitHelper(self.project_path)
        
        if self.operation == "pull_rebase":
            self.progress.emit(f"⬇️ 正在从 {self.remote} 拉取...")
            success, msg = git.pull_rebase(self.remote)
            if success:
                self.progress.emit(f"✅ {msg}")
            else:
                self.progress.emit(f"❌ {msg}")
                if "conflict" in msg.lower():
                    self.progress.emit("请使用 VS Code 解决冲突后重试")
            self.finished.emit(success, msg)
        
        elif self.operation == "force_push":
            self.progress.emit(f"⬆️ 正在强制推送到 {self.remote}...")
            success, msg = git.force_push(self.remote)
            if success:
                self.progress.emit(f"✅ {msg}")
            else:
                self.progress.emit(f"❌ {msg}")
            self.finished.emit(success, msg)
        
        elif self.operation == "push_all":
            self.progress.emit("📤 推送到所有远程仓库...")
            remotes = git.get_remotes()
            branch = self.branch or git.get_current_branch() or "main"
            success_count = 0
            
            for remote in remotes:
                name = remote.get("name", "")
                self.progress.emit(f"  → {name}...")
                
                if git.push(name, branch):
                    self.progress.emit(f"    ✅ 成功")
                    success_count += 1
                else:
                    self.progress.emit(f"    ⚠️ 失败 (可能需要先拉取)")
            
            self.finished.emit(
                success_count == len(remotes),
                f"完成 {success_count}/{len(remotes)}"
            )
        
        elif self.operation == "commit_and_push_all":
            changelog = self.remote  # Reuse remote param for changelog message
            
            # Check for changes
            if not git.has_local_changes():
                self.progress.emit("⚠️ 没有需要提交的修改")
                self.finished.emit(False, "没有修改")
                return
            
            # Stage all changes
            self.progress.emit("📦 暂存所有修改...")
            try:
                git._run_git(["add", "-A"])
            except Exception as e:
                self.progress.emit(f"❌ 暂存失败: {e}")
                self.finished.emit(False, str(e))
                return
            
            # Commit
            self.progress.emit(f"💾 提交修改: {changelog[:50]}...")
            if not git.commit(changelog):
                self.progress.emit("❌ 提交失败")
                self.finished.emit(False, "提交失败")
                return
            self.progress.emit("✅ 提交成功")
            
            # Push to all remotes
            self.progress.emit("📤 推送到所有远程仓库...")
            remotes = git.get_remotes()
            branch = git.get_current_branch() or "main"
            success_count = 0
            
            for remote in remotes:
                name = remote.get("name", "")
                self.progress.emit(f"  → {name}...")
                
                if git.push(name, branch):
                    self.progress.emit(f"    ✅ 成功")
                    success_count += 1
                else:
                    self.progress.emit(f"    ⚠️ 失败 (可能需要先拉取)")
            
            self.finished.emit(
                success_count == len(remotes),
                f"提交并推送完成 {success_count}/{len(remotes)}"
            )
