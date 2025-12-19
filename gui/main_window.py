"""
Git Version Manager - Main Window
"""
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QFrame,
    QSplitter, QMessageBox, QFileDialog, QMenu, QAction, QProgressBar,
    QTextEdit, QGroupBox, QComboBox, QLineEdit, QDialog, QFormLayout,
    QDialogButtonBox, QCheckBox, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QColor, QFont, QDragEnterEvent, QDropEvent

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.git_helper import GitHelper
from core.version_parser import detect_project_type, get_parser, VersionParser
from core.packager import Packager
from core.publisher import get_publisher
from core.config_manager import ConfigManager


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
        
        # Local version
        self.progress.emit("🏷️ 读取本地版本...")
        parser = get_parser(self.project_type)
        if parser:
            version_file = os.path.join(self.project_path, parser.get_version_file())
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                local_version = parser.get_version(content)
                if local_version:
                    result["local_version"] = local_version
                    self.progress.emit(f"  本地版本: {VersionParser.version_to_string(local_version)}")
                    self.update_label.emit("local_version", VersionParser.version_to_string(local_version), "#333")
        
        # Per-platform remote versions
        platform_status = {}
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
                parser.get_version_file() if parser else "__init__.py",
                remote=remote_name
            )
            
            if remote_content and parser:
                remote_version = parser.get_version(remote_content)
                if remote_version:
                    version_str = VersionParser.version_to_string(remote_version)
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
                            color = "#333"
                    else:
                        status = version_str
                        color = "#333"
                    
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
        
        try:
            packager = Packager(self.project_path, self.project_name, self.archive_path)
            
            # Use dist packaging for python_app (compiled exe projects)
            if self.project_type == "python_app":
                self.progress.emit("📂 打包 dist/ 编译文件...")
                zip_path = packager.create_dist_zip(self.version)
            else:
                self.progress.emit("📂 收集源文件...")
                zip_path = packager.create_zip(self.version)
            
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
        
        # Get local version
        local_version_str = ""
        parser = get_parser(project_type)
        if parser:
            version_file = os.path.join(path, parser.get_version_file())
            if os.path.exists(version_file):
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    local_version = parser.get_version(content)
                    if local_version:
                        local_version_str = VersionParser.version_to_string(local_version)
                except:
                    pass
        
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
        icon = self.STATUS_ICONS.get(self.status, "❓")
        version_str = f" v{self.local_version}" if self.local_version else ""
        self.setText(f"{icon} {name}{version_str}")
    
    def set_status(self, status: str, local_version: str = None):
        self.status = status
        if local_version is not None:
            self.local_version = local_version
        self.update_display()
    
    def set_cached_status(self, platform_status: dict, has_changes: bool, ahead: int, behind: int):
        """Store cached detailed status info."""
        import datetime
        self.cached_status = {
            "has_changes": has_changes,
            "ahead": ahead,
            "behind": behind,
            "platform_status": platform_status,
            "last_check": datetime.datetime.now()
        }


class SettingsDialog(QDialog):
    """Settings dialog."""
    
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabs
        tabs = QTabWidget()
        
        # General tab
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        
        self.archive_path_edit = QLineEdit(self.config.get_archive_path())
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_archive_path)
        archive_layout = QHBoxLayout()
        archive_layout.addWidget(self.archive_path_edit)
        archive_layout.addWidget(browse_btn)
        general_layout.addRow("打包存储路径:", archive_layout)
        
        tabs.addTab(general_tab, "常规")
        
        # Tokens tab
        tokens_tab = QWidget()
        tokens_layout = QFormLayout(tokens_tab)
        
        self.github_token_edit = QLineEdit(self.config.get_token("github"))
        self.github_token_edit.setEchoMode(QLineEdit.Password)
        tokens_layout.addRow("GitHub Token:", self.github_token_edit)
        
        self.gitee_token_edit = QLineEdit(self.config.get_token("gitee"))
        self.gitee_token_edit.setEchoMode(QLineEdit.Password)
        tokens_layout.addRow("Gitee Token:", self.gitee_token_edit)
        
        self.gitea_url_edit = QLineEdit(self.config.get_gitea_url())
        tokens_layout.addRow("Gitea URL:", self.gitea_url_edit)
        
        self.gitea_token_edit = QLineEdit(self.config.get_token("gitea"))
        self.gitea_token_edit.setEchoMode(QLineEdit.Password)
        tokens_layout.addRow("Gitea Token:", self.gitea_token_edit)
        
        tabs.addTab(tokens_tab, "API Tokens")
        
        layout.addWidget(tabs)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def browse_archive_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择打包存储目录")
        if path:
            self.archive_path_edit.setText(path)
    
    def accept(self):
        self.config.set_archive_path(self.archive_path_edit.text())
        self.config.set_token("github", self.github_token_edit.text())
        self.config.set_token("gitee", self.gitee_token_edit.text())
        self.config.set_token("gitea", self.gitea_token_edit.text(), self.gitea_url_edit.text())
        super().accept()


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


class SyncDialog(QDialog):
    """Dialog for git sync operations with per-remote status."""
    
    def __init__(self, project_path: str, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.git = GitHelper(project_path)
        self.sync_worker = None
        self.operation_worker = None
        self.setWindowTitle("Git 同步管理")
        self.setMinimumSize(650, 450)
        self.setup_ui()
        # Start async status check after dialog shows
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self.refresh_status_async)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"📂 {os.path.basename(self.project_path)}")
        header.setFont(QFont("", 14, QFont.Bold))
        layout.addWidget(header)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # === Tab 1: Status ===
        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)
        
        self.remotes_table = QListWidget()
        self.remotes_table.setMinimumHeight(200)
        status_layout.addWidget(self.remotes_table)
        
        self.refresh_btn = QPushButton("🔄 刷新状态")
        self.refresh_btn.clicked.connect(self.refresh_status_async)
        status_layout.addWidget(self.refresh_btn)
        
        self.tabs.addTab(status_tab, "📊 状态")
        
        # === Tab 2: Commit ===
        commit_tab = QWidget()
        commit_layout = QVBoxLayout(commit_tab)
        
        commit_layout.addWidget(QLabel("更新日志 (Changelog):"))
        self.changelog_input = QTextEdit()
        self.changelog_input.setPlaceholderText("请输入本次提交的更新内容...")
        commit_layout.addWidget(self.changelog_input)
        
        self.commit_push_btn = QPushButton("💾 提交并推送到所有远程")
        self.commit_push_btn.setStyleSheet("background-color: #4dabf5; color: white; padding: 10px;")
        self.commit_push_btn.clicked.connect(self.do_commit_and_push_all)
        commit_layout.addWidget(self.commit_push_btn)
        
        self.tabs.addTab(commit_tab, "💾 提交")
        
        # === Tab 3: Sync ===
        sync_tab = QWidget()
        sync_layout = QVBoxLayout(sync_tab)
        
        # Remote selector
        remote_layout = QHBoxLayout()
        remote_layout.addWidget(QLabel("选择远程:"))
        self.remote_combo = QComboBox()
        self.remote_combo.setMinimumWidth(200)
        remote_layout.addWidget(self.remote_combo)
        remote_layout.addStretch()
        sync_layout.addLayout(remote_layout)
        
        # Pull button
        self.pull_btn = QPushButton("⬇️ 拉取 (Pull Rebase)")
        self.pull_btn.clicked.connect(self.do_pull_rebase)
        sync_layout.addWidget(self.pull_btn)
        
        # Push all button
        self.push_all_btn = QPushButton("📤 推送到所有远程")
        self.push_all_btn.clicked.connect(self.do_push_all)
        sync_layout.addWidget(self.push_all_btn)
        
        # Force push button
        self.force_push_btn = QPushButton("⬆️ 强制推送 (危险)")
        self.force_push_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        self.force_push_btn.clicked.connect(self.do_force_push)
        sync_layout.addWidget(self.force_push_btn)
        
        sync_layout.addStretch()
        self.tabs.addTab(sync_tab, "🔄 同步")
        
        # === Tab 4: Package & Publish ===
        package_tab = QWidget()
        package_layout = QVBoxLayout(package_tab)
        
        # Package section
        package_layout.addWidget(QLabel("📦 打包项目"))
        self.package_btn = QPushButton("📦 创建 ZIP 包")
        self.package_btn.clicked.connect(self.do_package)
        package_layout.addWidget(self.package_btn)
        
        package_layout.addWidget(QLabel(""))  # Spacer
        
        # Publish section
        package_layout.addWidget(QLabel("🚀 发布版本"))
        self.publish_btn = QPushButton("🚀 发布到配置的平台")
        self.publish_btn.setStyleSheet("background-color: #51cf66; color: white;")
        self.publish_btn.clicked.connect(self.do_publish)
        package_layout.addWidget(self.publish_btn)
        
        package_layout.addStretch()
        self.tabs.addTab(package_tab, "📦 打包发布")
        
        # === Tab 5: Conflict ===
        conflict_tab = QWidget()
        conflict_layout = QVBoxLayout(conflict_tab)
        
        self.conflict_label = QLabel("🔄 检查中...")
        self.conflict_label.setStyleSheet("color: gray; font-size: 14px;")
        conflict_layout.addWidget(self.conflict_label)
        
        self.open_vscode_btn = QPushButton("📝 用 VS Code 解决冲突")
        self.open_vscode_btn.clicked.connect(self.open_vscode)
        self.open_vscode_btn.setEnabled(False)
        conflict_layout.addWidget(self.open_vscode_btn)
        
        self.abort_btn = QPushButton("❌ 中止操作")
        self.abort_btn.clicked.connect(self.abort_operation)
        self.abort_btn.setEnabled(False)
        conflict_layout.addWidget(self.abort_btn)
        
        conflict_layout.addStretch()
        self.tabs.addTab(conflict_tab, "⚠️ 冲突")
        
        # Log (always visible at bottom, stretches with window)
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(80)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group, 1)  # stretch factor 1
        
        # Close button
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def log(self, msg: str):
        self.log_text.append(msg)
    
    def set_operation_buttons_enabled(self, enabled: bool):
        """Enable/disable all operation buttons."""
        self.pull_btn.setEnabled(enabled)
        self.force_push_btn.setEnabled(enabled)
        self.push_all_btn.setEnabled(enabled)
        self.commit_push_btn.setEnabled(enabled)
        self.package_btn.setEnabled(enabled)
        self.publish_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
    
    def refresh_status_async(self):
        """Refresh status for all remotes asynchronously."""
        if self.sync_worker and self.sync_worker.isRunning():
            self.log("⏳ 正在检查中，请稍候...")
            return
        
        self.remotes_table.clear()
        self.remote_combo.clear()
        self.refresh_btn.setEnabled(False)
        self.log("🔄 开始检查远程状态...")
        
        self.sync_worker = SyncStatusWorker(self.project_path)
        self.sync_worker.progress.connect(self.log)
        self.sync_worker.remote_found.connect(self.on_remote_found)
        self.sync_worker.finished.connect(self.on_status_check_finished)
        self.sync_worker.start()
    
    def on_remote_found(self, result: dict):
        """Handle a single remote status result."""
        name = result["name"]
        platform = result["platform"]
        ahead = result["ahead"]
        behind = result["behind"]
        error = result.get("error")
        
        if error:
            status_text = f"❌ {error}"
        elif ahead == 0 and behind == 0:
            status_text = "✅ 已同步"
        else:
            parts = []
            if ahead > 0:
                parts.append(f"⬆️ 领先 {ahead}")
            if behind > 0:
                parts.append(f"⬇️ 落后 {behind}")
            status_text = " | ".join(parts)
        
        item_text = f"[{platform.upper()}] {name}: {status_text}"
        item = QListWidgetItem(item_text)
        
        if behind > 0:
            item.setForeground(QColor("orange"))
        elif ahead > 0:
            item.setForeground(QColor("blue"))
        elif not error:
            item.setForeground(QColor("green"))
        else:
            item.setForeground(QColor("red"))
        
        self.remotes_table.addItem(item)
        self.remote_combo.addItem(f"{name} ({platform})", name)
    
    def on_status_check_finished(self):
        """Handle status check completion."""
        self.refresh_btn.setEnabled(True)
        self.check_conflicts()
    
    def check_conflicts(self):
        """Check and display conflict status."""
        if self.git.has_merge_conflicts():
            conflicts = self.git.get_conflict_files()
            self.conflict_label.setText(f"⚠️ 检测到 {len(conflicts)} 个冲突文件")
            self.conflict_label.setStyleSheet("color: red; font-weight: bold;")
            self.open_vscode_btn.setEnabled(True)
            self.abort_btn.setEnabled(True)
        else:
            self.conflict_label.setText("✅ 无冲突")
            self.conflict_label.setStyleSheet("color: green;")
            self.open_vscode_btn.setEnabled(False)
            self.abort_btn.setEnabled(False)
    
    def do_pull_rebase(self):
        """Pull with rebase from selected remote (async)."""
        remote = self.remote_combo.currentData()
        if not remote:
            return
        
        if self.operation_worker and self.operation_worker.isRunning():
            self.log("⏳ 操作正在进行中...")
            return
        
        self.set_operation_buttons_enabled(False)
        
        self.operation_worker = SyncOperationWorker(
            self.project_path, "pull_rebase", remote=remote
        )
        self.operation_worker.progress.connect(self.log)
        self.operation_worker.finished.connect(self.on_operation_finished)
        self.operation_worker.start()
    
    def do_force_push(self):
        """Force push to selected remote (async)."""
        remote = self.remote_combo.currentData()
        if not remote:
            return
        
        reply = QMessageBox.warning(
            self, "⚠️ 危险操作",
            f"强制推送将覆盖远程 {remote} 上的更改！\n\n"
            "这可能导致他人的提交丢失。确定继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        if self.operation_worker and self.operation_worker.isRunning():
            self.log("⏳ 操作正在进行中...")
            return
        
        self.set_operation_buttons_enabled(False)
        
        self.operation_worker = SyncOperationWorker(
            self.project_path, "force_push", remote=remote
        )
        self.operation_worker.progress.connect(self.log)
        self.operation_worker.finished.connect(self.on_operation_finished)
        self.operation_worker.start()
    
    def do_push_all(self):
        """Push to all remotes (async)."""
        if self.operation_worker and self.operation_worker.isRunning():
            self.log("⏳ 操作正在进行中...")
            return
        
        self.set_operation_buttons_enabled(False)
        
        self.operation_worker = SyncOperationWorker(
            self.project_path, "push_all"
        )
        self.operation_worker.progress.connect(self.log)
        self.operation_worker.finished.connect(self.on_operation_finished)
        self.operation_worker.start()
    
    def do_commit_and_push_all(self):
        """Commit all changes with changelog and push to all remotes (async)."""
        changelog = self.changelog_input.toPlainText().strip()
        
        if not changelog:
            QMessageBox.warning(self, "提示", "请输入更新日志内容")
            return
        
        if self.operation_worker and self.operation_worker.isRunning():
            self.log("⏳ 操作正在进行中...")
            return
        
        self.set_operation_buttons_enabled(False)
        
        # Pass changelog through the remote parameter
        self.operation_worker = SyncOperationWorker(
            self.project_path, "commit_and_push_all", remote=changelog
        )
        self.operation_worker.progress.connect(self.log)
        self.operation_worker.finished.connect(self.on_commit_push_finished)
        self.operation_worker.start()
    
    def on_commit_push_finished(self, success: bool, msg: str):
        """Handle commit+push completion."""
        self.set_operation_buttons_enabled(True)
        if success:
            self.changelog_input.clear()  # Clear input on success
        self.refresh_status_async()
    
    def on_operation_finished(self, success: bool, msg: str):
        """Handle operation completion."""
        self.set_operation_buttons_enabled(True)
        self.refresh_status_async()
    
    def do_package(self):
        """Package the project as ZIP."""
        main_window = self.parent()
        if main_window and hasattr(main_window, 'package_project'):
            self.log("📦 开始打包...")
            main_window.package_project()
        else:
            self.log("❌ 无法访问打包功能")
    
    def do_publish(self):
        """Publish project to configured platforms."""
        main_window = self.parent()
        if main_window and hasattr(main_window, 'publish_project'):
            self.log("🚀 开始发布...")
            main_window.publish_project()
        else:
            self.log("❌ 无法访问发布功能")
    
    def open_vscode(self):
        """Open in VS Code for conflict resolution."""
        if self.git.open_in_vscode():
            self.log("📝 已在 VS Code 中打开")
        else:
            self.log("❌ 无法打开 VS Code")
    
    def abort_operation(self):
        """Abort ongoing merge/rebase."""
        self.log("❌ 正在中止操作...")
        
        if self.git.abort_rebase():
            self.log("✅ Rebase 已中止")
        elif self.git.abort_merge():
            self.log("✅ Merge 已中止")
        else:
            self.log("⚠️ 没有进行中的操作")
        
        self.refresh_status_async()


class ProjectDialog(QDialog):
    """Dialog to add or edit a project with git remote integration."""
    
    PLATFORM_URLS = {
        "github": "https://github.com/{repo}.git",
        "gitee": "https://gitee.com/{repo}.git",
        "gitea": "{base_url}/{repo}.git"
    }
    
    def __init__(self, parent=None, project_data=None, gitea_base_url=""):
        super().__init__(parent)
        self.is_edit_mode = project_data is not None
        self.setWindowTitle("编辑项目" if self.is_edit_mode else "添加项目")
        self.setMinimumWidth(600)
        self.project_data = project_data or {}
        self.gitea_base_url = gitea_base_url
        self.original_remotes = []  # Store original git remotes for comparison
        self.setup_ui()
        
        # Load git remotes if editing
        if self.is_edit_mode:
            self.load_git_remotes()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Path section
        path_group = QGroupBox("项目路径")
        path_layout = QHBoxLayout(path_group)
        self.path_edit = QLineEdit(self.project_data.get("path", ""))
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_path)
        if self.is_edit_mode:
            self.path_edit.setReadOnly(True)
            browse_btn.setEnabled(False)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)
        layout.addWidget(path_group)
        
        # Type section
        type_group = QGroupBox("项目类型")
        type_layout = QHBoxLayout(type_group)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["auto", "blender_addon", "python_app", "npm", "python", "custom"])
        current_type = self.project_data.get("type", "auto")
        index = self.type_combo.findText(current_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        type_layout.addWidget(self.type_combo)
        layout.addWidget(type_group)
        
        # Git Remotes section
        remotes_group = QGroupBox("Git 远程仓库 (自动读取自 .git/config)")
        remotes_layout = QVBoxLayout(remotes_group)
        
        # Info label
        info_label = QLabel("⚠️ 修改此处将直接更新项目的 .git/config 文件")
        info_label.setStyleSheet("color: orange;")
        remotes_layout.addWidget(info_label)
        
        # Remote entries
        self.remote_widgets = {}
        
        # GitHub
        github_layout = QHBoxLayout()
        self.github_check = QCheckBox("GitHub")
        self.github_check.setFixedWidth(80)
        self.github_repo_edit = QLineEdit()
        self.github_repo_edit.setPlaceholderText("username/repo")
        self.github_url_label = QLabel("https://github.com/...")
        self.github_url_label.setStyleSheet("color: gray; font-size: 10px;")
        self.github_repo_edit.textChanged.connect(lambda t: self.update_url_preview("github", t))
        github_layout.addWidget(self.github_check)
        github_layout.addWidget(self.github_repo_edit)
        v_layout = QVBoxLayout()
        v_layout.addLayout(github_layout)
        v_layout.addWidget(self.github_url_label)
        remotes_layout.addLayout(v_layout)
        
        # Gitee
        gitee_layout = QHBoxLayout()
        self.gitee_check = QCheckBox("Gitee")
        self.gitee_check.setFixedWidth(80)
        self.gitee_repo_edit = QLineEdit()
        self.gitee_repo_edit.setPlaceholderText("username/repo")
        self.gitee_url_label = QLabel("https://gitee.com/...")
        self.gitee_url_label.setStyleSheet("color: gray; font-size: 10px;")
        self.gitee_repo_edit.textChanged.connect(lambda t: self.update_url_preview("gitee", t))
        gitee_layout.addWidget(self.gitee_check)
        gitee_layout.addWidget(self.gitee_repo_edit)
        v_layout2 = QVBoxLayout()
        v_layout2.addLayout(gitee_layout)
        v_layout2.addWidget(self.gitee_url_label)
        remotes_layout.addLayout(v_layout2)
        
        # Gitea
        gitea_layout = QHBoxLayout()
        self.gitea_check = QCheckBox("Gitea")
        self.gitea_check.setFixedWidth(80)
        self.gitea_repo_edit = QLineEdit()
        self.gitea_repo_edit.setPlaceholderText("username/repo")
        self.gitea_url_label = QLabel("Gitea URL...")
        self.gitea_url_label.setStyleSheet("color: gray; font-size: 10px;")
        self.gitea_repo_edit.textChanged.connect(lambda t: self.update_url_preview("gitea", t))
        gitea_layout.addWidget(self.gitea_check)
        gitea_layout.addWidget(self.gitea_repo_edit)
        v_layout3 = QVBoxLayout()
        v_layout3.addLayout(gitea_layout)
        v_layout3.addWidget(self.gitea_url_label)
        remotes_layout.addLayout(v_layout3)
        
        layout.addWidget(remotes_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def update_url_preview(self, platform: str, repo: str):
        """Update URL preview label."""
        if platform == "github":
            url = f"https://github.com/{repo}.git" if repo else "https://github.com/..."
            self.github_url_label.setText(url)
        elif platform == "gitee":
            url = f"https://gitee.com/{repo}.git" if repo else "https://gitee.com/..."
            self.gitee_url_label.setText(url)
        elif platform == "gitea":
            base = self.gitea_base_url or "https://gitea.example.com"
            url = f"{base}/{repo}.git" if repo else f"{base}/..."
            self.gitea_url_label.setText(url)
    
    def load_git_remotes(self):
        """Load git remotes from the project's .git/config."""
        path = self.project_data.get("path", "")
        if not path:
            return
        
        git = GitHelper(path)
        if not git.is_git_repo():
            return
        
        remotes = git.get_remotes_with_details()
        self.original_remotes = remotes
        
        # Map remotes to UI
        for remote in remotes:
            platform = remote.get("platform")
            repo = remote.get("repo", "")
            
            if platform == "github":
                self.github_check.setChecked(True)
                self.github_repo_edit.setText(repo)
            elif platform == "gitee":
                self.gitee_check.setChecked(True)
                self.gitee_repo_edit.setText(repo)
            elif platform == "gitea":
                self.gitea_check.setChecked(True)
                self.gitea_repo_edit.setText(repo)
        
        # Also load from project_data if not found in git (for publish_to config)
        publish_to = self.project_data.get("publish_to", [])
        if "github" in publish_to and not self.github_check.isChecked():
            self.github_check.setChecked(True)
            self.github_repo_edit.setText(self.project_data.get("github_repo", ""))
        if "gitee" in publish_to and not self.gitee_check.isChecked():
            self.gitee_check.setChecked(True)
            self.gitee_repo_edit.setText(self.project_data.get("gitee_repo", ""))
        if "gitea" in publish_to and not self.gitea_check.isChecked():
            self.gitea_check.setChecked(True)
            self.gitea_repo_edit.setText(self.project_data.get("gitea_repo", ""))
    
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择项目目录")
        if path:
            self.path_edit.setText(path)
            # Auto-detect type
            detected = detect_project_type(path)
            if detected:
                index = self.type_combo.findText(detected)
                if index >= 0:
                    self.type_combo.setCurrentIndex(index)
            # Try to load git remotes
            self.project_data["path"] = path
            self.load_git_remotes()
    
    def validate_repo_format(self, repo: str) -> bool:
        """Validate repo format is username/repo."""
        import re
        if not repo:
            return True  # Empty is OK (will be skipped)
        return bool(re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', repo))
    
    def validate_and_accept(self):
        path = self.path_edit.text()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "错误", "请选择有效的项目目录")
            return
        
        # Validate repo formats
        github_repo = self.github_repo_edit.text().strip()
        gitee_repo = self.gitee_repo_edit.text().strip()
        gitea_repo = self.gitea_repo_edit.text().strip()
        
        if self.github_check.isChecked() and not self.validate_repo_format(github_repo):
            QMessageBox.warning(self, "格式错误", "GitHub 仓库格式应为: username/repo")
            return
        if self.gitee_check.isChecked() and not self.validate_repo_format(gitee_repo):
            QMessageBox.warning(self, "格式错误", "Gitee 仓库格式应为: username/repo")
            return
        if self.gitea_check.isChecked() and not self.validate_repo_format(gitea_repo):
            QMessageBox.warning(self, "格式错误", "Gitea 仓库格式应为: username/repo")
            return
        
        # Update git remotes if in edit mode
        if self.is_edit_mode:
            self.update_git_remotes(path, github_repo, gitee_repo, gitea_repo)
        
        publish_to = []
        if self.github_check.isChecked():
            publish_to.append("github")
        if self.gitee_check.isChecked():
            publish_to.append("gitee")
        if self.gitea_check.isChecked():
            publish_to.append("gitea")
        
        project_type = self.type_combo.currentText()
        if project_type == "auto":
            project_type = detect_project_type(path) or "custom"
        
        self.project_data = {
            "path": path,
            "type": project_type,
            "publish_to": publish_to,
            "github_repo": github_repo,
            "gitee_repo": gitee_repo,
            "gitea_repo": gitea_repo
        }
        self.accept()
    
    def update_git_remotes(self, path: str, github_repo: str, gitee_repo: str, gitea_repo: str):
        """Update git remotes based on UI changes."""
        git = GitHelper(path)
        if not git.is_git_repo():
            return
        
        # Build current state from UI
        new_remotes = {}
        if self.github_check.isChecked() and github_repo:
            new_remotes["origin"] = f"https://github.com/{github_repo}.git"
        if self.gitee_check.isChecked() and gitee_repo:
            # Use a different remote name for gitee
            new_remotes["gitee"] = f"https://gitee.com/{gitee_repo}.git"
        if self.gitea_check.isChecked() and gitea_repo:
            base = self.gitea_base_url or "https://gitea.example.com"
            new_remotes["gitea"] = f"{base}/{gitea_repo}.git"
        
        # Get existing remotes
        existing = {r["name"]: r["url"] for r in git.get_remotes()}
        
        # Update or add remotes
        for name, url in new_remotes.items():
            if name in existing:
                if existing[name] != url:
                    git.set_remote_url(name, url)
            else:
                git.add_remote(name, url)


# Alias for backwards compatibility
AddProjectDialog = ProjectDialog


class MainWindow(QMainWindow):
    """Main application window."""
    
    AUTO_REFRESH_INTERVALS = {
        "不自动检查": 0,
        "5分钟": 5 * 60 * 1000,
        "15分钟": 15 * 60 * 1000,
        "30分钟": 30 * 60 * 1000
    }
    
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.current_project = None
        self.current_item = None
        self.worker = None
        
        # Auto-refresh timer
        from PyQt5.QtCore import QTimer
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.on_auto_refresh)
        
        self.setWindowTitle("Git Version Manager")
        self.setMinimumSize(900, 600)
        
        # Set window icon (works in both dev and bundled mode)
        from PyQt5.QtGui import QIcon
        import sys
        if getattr(sys, 'frozen', False):
            # Running as bundled exe
            base_path = sys._MEIPASS
        else:
            # Running as script
            base_path = os.path.dirname(os.path.dirname(__file__))
        icon_path = os.path.join(base_path, "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setAcceptDrops(True)
        
        self.setup_ui()
        self.load_projects()
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        
        # Left panel - Project list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.project_list = QListWidget()
        self.project_list.setMinimumWidth(200)
        self.project_list.itemClicked.connect(self.on_project_selected)
        self.project_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(self.show_project_context_menu)
        left_layout.addWidget(self.project_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ 添加")
        add_btn.clicked.connect(self.add_project)
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedWidth(40)
        settings_btn.clicked.connect(self.open_settings)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(settings_btn)
        left_layout.addLayout(btn_layout)
        
        # Right panel - Project details
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Project info
        info_group = QGroupBox("项目信息")
        info_layout = QFormLayout(info_group)
        
        self.name_label = QLabel("-")
        self.name_label.setFont(QFont("", 12, QFont.Bold))
        info_layout.addRow("名称:", self.name_label)
        
        self.path_label = QLabel("-")
        info_layout.addRow("路径:", self.path_label)
        
        self.type_label = QLabel("-")
        info_layout.addRow("类型:", self.type_label)
        
        self.local_version_label = QLabel("-")
        info_layout.addRow("本地版本:", self.local_version_label)
        
        # Per-platform remote versions
        self.remote_versions_widget = QWidget()
        remote_versions_layout = QVBoxLayout(self.remote_versions_widget)
        remote_versions_layout.setContentsMargins(0, 0, 0, 0)
        remote_versions_layout.setSpacing(2)
        
        self.github_version_label = QLabel("▶ GitHub: -")
        self.github_version_label.setStyleSheet("color: #333;")
        remote_versions_layout.addWidget(self.github_version_label)
        
        self.gitee_version_label = QLabel("▶ Gitee: -")
        self.gitee_version_label.setStyleSheet("color: #333;")
        remote_versions_layout.addWidget(self.gitee_version_label)
        
        self.gitea_version_label = QLabel("▶ Gitea: -")
        self.gitea_version_label.setStyleSheet("color: #333;")
        remote_versions_layout.addWidget(self.gitea_version_label)
        
        info_layout.addRow("远程版本:", self.remote_versions_widget)
        
        self.status_label = QLabel("-")
        info_layout.addRow("状态:", self.status_label)
        
        right_layout.addWidget(info_group)
        
        # Actions - only 4 core functions
        actions_group = QGroupBox("操作")
        actions_layout = QHBoxLayout(actions_group)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_project)
        actions_layout.addWidget(self.refresh_btn)
        
        self.bump_btn = QPushButton("⬆️ 版本+1")
        self.bump_btn.clicked.connect(self.bump_version)
        actions_layout.addWidget(self.bump_btn)
        
        self.sync_btn = QPushButton("🔄 同步管理")
        self.sync_btn.clicked.connect(self.open_sync_dialog)
        actions_layout.addWidget(self.sync_btn)
        
        # Auto-refresh dropdown
        actions_layout.addWidget(QLabel("自动刷新:"))
        self.auto_refresh_combo = QComboBox()
        self.auto_refresh_combo.addItems(list(self.AUTO_REFRESH_INTERVALS.keys()))
        self.auto_refresh_combo.currentTextChanged.connect(self.on_auto_refresh_changed)
        actions_layout.addWidget(self.auto_refresh_combo)
        
        right_layout.addWidget(actions_group)
        
        # Log (stretches with window)
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(80)
        log_layout.addWidget(self.log_text)
        
        right_layout.addWidget(log_group, 1)  # stretch factor 1
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)
        
        right_layout.addStretch()
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 650])
        
        main_layout.addWidget(splitter)
    
    def log(self, message: str):
        """Add message to log."""
        self.log_text.append(message)
    
    def load_projects(self):
        """Load projects from config."""
        self.project_list.clear()
        self.status_workers = []  # Track workers for parallel check
        
        projects = self.config.get_projects()
        for project in projects:
            item = ProjectItem(project)
            item.set_status("checking")  # Show checking status
            self.project_list.addItem(item)
        
        # Start parallel status check for all projects
        if projects:
            self.log(f"🔍 正在检查 {len(projects)} 个项目状态...")
            self.check_all_projects_parallel()
    
    def check_all_projects_parallel(self):
        """Check status of all projects in parallel."""
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if isinstance(item, ProjectItem):
                worker = ProjectStatusWorker(item.project_data)
                worker.finished.connect(self.on_project_status_checked)
                self.status_workers.append(worker)
                worker.start()
    
    def on_project_status_checked(self, path: str, status: str, local_version: str):
        """Handle status check result for a single project."""
        # Find the matching project item
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if isinstance(item, ProjectItem):
                if item.project_data.get("path") == path:
                    item.set_status(status, local_version)
                    break
        
        # Check if all done
        all_done = all(
            not w.isRunning() for w in getattr(self, 'status_workers', [])
        )
        if all_done and hasattr(self, 'status_workers') and self.status_workers:
            self.log("✅ 所有项目状态检查完成")
            self.status_workers = []
    
    def on_auto_refresh_changed(self, text: str):
        """Handle auto-refresh interval change."""
        interval = self.AUTO_REFRESH_INTERVALS.get(text, 0)
        
        if interval > 0:
            self.auto_refresh_timer.start(interval)
            self.log(f"⏱️ 自动刷新已启用: {text}")
        else:
            self.auto_refresh_timer.stop()
            self.log("⏱️ 自动刷新已关闭")
    
    def on_auto_refresh(self):
        """Handle auto-refresh timer timeout."""
        self.log("⏱️ 自动刷新中...")
        # Re-check all projects in parallel
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if isinstance(item, ProjectItem):
                item.set_status("checking")
        self.check_all_projects_parallel()
    
    def add_project(self):
        """Add a new project."""
        dialog = AddProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.project_data:
            if self.config.add_project(dialog.project_data):
                self.load_projects()
                self.log(f"添加项目: {dialog.project_data['path']}")
            else:
                QMessageBox.warning(self, "错误", "项目已存在")
    
    def on_project_selected(self, item: ProjectItem):
        """Handle project selection - display cached status."""
        self.current_project = item.project_data
        self.current_item = item  # Store reference to current item
        self.update_project_display()
        
        # Display cached status from ProjectItem
        if item.local_version:
            self.local_version_label.setText(item.local_version)
        else:
            self.local_version_label.setText("-")
        
        # Display cached platform status
        cached = item.cached_status
        platform_status = cached.get("platform_status", {})
        
        if "github" in platform_status:
            status, color = platform_status["github"]
            self.github_version_label.setText(f"▶ GitHub: {status}")
            self.github_version_label.setStyleSheet(f"color: {color};")
        else:
            self.github_version_label.setText("▶ GitHub: -")
            self.github_version_label.setStyleSheet("color: gray;")
        
        if "gitee" in platform_status:
            status, color = platform_status["gitee"]
            self.gitee_version_label.setText(f"▶ Gitee: {status}")
            self.gitee_version_label.setStyleSheet(f"color: {color};")
        else:
            self.gitee_version_label.setText("▶ Gitee: -")
            self.gitee_version_label.setStyleSheet("color: gray;")
        
        if "gitea" in platform_status:
            status, color = platform_status["gitea"]
            self.gitea_version_label.setText(f"▶ Gitea: {status}")
            self.gitea_version_label.setStyleSheet(f"color: {color};")
        else:
            self.gitea_version_label.setText("▶ Gitea: -")
            self.gitea_version_label.setStyleSheet("color: gray;")
        
        # Display cached git status
        has_changes = cached.get("has_changes", False)
        ahead = cached.get("ahead", 0)
        behind = cached.get("behind", 0)
        last_check = cached.get("last_check")
        
        if last_check:
            status_parts = []
            if has_changes:
                status_parts.append("⚠️ 有未提交修改")
            if ahead > 0:
                status_parts.append(f"⬆️ 领先 {ahead} 个提交")
            if behind > 0:
                status_parts.append(f"⬇️ 落后 {behind} 个提交")
            if not status_parts:
                status_parts.append("✅ 已同步")
            self.status_label.setText(" | ".join(status_parts))
        else:
            self.status_label.setText("点击刷新按钮检查详细状态")
    
    def update_project_display(self):
        """Update the project info display."""
        if not self.current_project:
            return
        
        path = self.current_project.get("path", "")
        self.name_label.setText(os.path.basename(path))
        self.path_label.setText(path)
        self.type_label.setText(self.current_project.get("type", "unknown"))
    
    def refresh_project(self):
        """Refresh project status asynchronously."""
        if not self.current_project:
            return
        
        # Prevent multiple simultaneous refreshes
        if hasattr(self, 'refresh_worker') and self.refresh_worker and self.refresh_worker.isRunning():
            self.log("⏳ 刷新正在进行中...")
            return
        
        path = self.current_project.get("path", "")
        project_type = self.current_project.get("type", "")
        
        self.log(f"🔄 刷新项目: {os.path.basename(path)}")
        self.status_label.setText("🔄 正在刷新...")
        self.refresh_btn.setEnabled(False)
        
        # Create and start worker
        self.refresh_worker = RefreshWorker(path, project_type)
        self.refresh_worker.progress.connect(self.log)
        self.refresh_worker.update_label.connect(self.on_refresh_update_label)
        self.refresh_worker.finished.connect(self.on_refresh_finished)
        self.refresh_worker.start()
    
    def on_refresh_update_label(self, label_name: str, text: str, color: str):
        """Handle label updates from worker thread."""
        if label_name == "local_version":
            self.local_version_label.setText(text)
            self.local_version_label.setStyleSheet(f"color: {color};")
    
    def on_refresh_finished(self, result: dict):
        """Handle refresh completion."""
        self.refresh_btn.setEnabled(True)
        
        platform_status = result.get("platform_status", {})
        has_changes = result.get("has_changes", False)
        ahead = result.get("ahead", 0)
        behind = result.get("behind", 0)
        
        # Update platform labels
        if "github" in platform_status:
            status, color = platform_status["github"]
            self.github_version_label.setText(f"▶ GitHub: {status}")
            self.github_version_label.setStyleSheet(f"color: {color};")
        else:
            self.github_version_label.setText("▶ GitHub: 未配置")
            self.github_version_label.setStyleSheet("color: gray;")
        
        if "gitee" in platform_status:
            status, color = platform_status["gitee"]
            self.gitee_version_label.setText(f"▶ Gitee: {status}")
            self.gitee_version_label.setStyleSheet(f"color: {color};")
        else:
            self.gitee_version_label.setText("▶ Gitee: 未配置")
            self.gitee_version_label.setStyleSheet("color: gray;")
        
        if "gitea" in platform_status:
            status, color = platform_status["gitea"]
            self.gitea_version_label.setText(f"▶ Gitea: {status}")
            self.gitea_version_label.setStyleSheet(f"color: {color};")
        else:
            self.gitea_version_label.setText("▶ Gitea: 未配置")
            self.gitea_version_label.setStyleSheet("color: gray;")
        
        # Overall status
        status_parts = []
        if has_changes:
            status_parts.append("⚠️ 有未提交修改")
        if ahead > 0:
            status_parts.append(f"⬆️ 领先 {ahead} 个提交")
        if behind > 0:
            status_parts.append(f"⬇️ 落后 {behind} 个提交")
        if not status_parts:
            status_parts.append("✅ 已同步")
        
        self.status_label.setText(" | ".join(status_parts))
        
        # Update list item status and cache
        current_item = self.project_list.currentItem()
        if isinstance(current_item, ProjectItem):
            # Update local version
            local_version = result.get("local_version")
            if local_version:
                local_version_str = VersionParser.version_to_string(local_version)
                current_item.local_version = local_version_str
            
            current_item.set_status(result.get("item_status", "unknown"))
            # Cache the detailed status
            current_item.set_cached_status(
                platform_status, has_changes, ahead, behind
            )
    
    def bump_version(self):
        """Bump the patch version."""
        if not self.current_project:
            return
        
        path = self.current_project.get("path", "")
        project_type = self.current_project.get("type", "")
        
        parser = get_parser(project_type)
        if not parser:
            self.log("❌ 无法解析版本文件")
            return
        
        version_file = os.path.join(path, parser.get_version_file())
        if not os.path.exists(version_file):
            self.log(f"❌ 版本文件不存在: {version_file}")
            return
        
        with open(version_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        current_version = parser.get_version(content)
        if not current_version:
            self.log("❌ 无法解析当前版本")
            return
        
        new_version = VersionParser.bump_patch(current_version)
        new_content = parser.set_version(content, new_version)
        
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        self.log(f"✅ 版本已更新: {VersionParser.version_to_string(current_version)} → {VersionParser.version_to_string(new_version)}")
        self.refresh_project()
    
    def package_project(self):
        """Package the project as ZIP asynchronously."""
        if not self.current_project:
            return
        
        # Prevent multiple simultaneous operations
        if hasattr(self, 'package_worker') and self.package_worker and self.package_worker.isRunning():
            self.log("⏳ 打包正在进行中...")
            return
        
        path = self.current_project.get("path", "")
        project_name = os.path.basename(path)
        project_type = self.current_project.get("type", "")
        
        # Get version
        parser = get_parser(project_type)
        version = "0.0.0"
        if parser:
            version_file = os.path.join(path, parser.get_version_file())
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                v = parser.get_version(content)
                if v:
                    version = VersionParser.version_to_string(v)
        
        archive_path = self.config.get_archive_path() or os.path.dirname(path)
        
        self.log(f"📦 开始打包 {project_name}...")
        
        # Create and start worker
        self.package_worker = PackageWorker(path, project_name, archive_path, version, project_type)
        self.package_worker.progress.connect(self.log)
        self.package_worker.finished.connect(self.on_package_finished)
        self.package_worker.start()
    
    def on_package_finished(self, success: bool, result: str):
        """Handle package completion."""
        if success:
            self.last_zip_path = result
    
    def publish_project(self):
        """Publish project to configured platforms asynchronously."""
        if not self.current_project:
            return
        
        # Prevent multiple simultaneous operations
        if hasattr(self, 'publish_worker') and self.publish_worker and self.publish_worker.isRunning():
            self.log("⏳ 发布正在进行中...")
            return
        
        path = self.current_project.get("path", "")
        project_name = os.path.basename(path)
        project_type = self.current_project.get("type", "")
        publish_to = self.current_project.get("publish_to", [])
        
        if not publish_to:
            QMessageBox.warning(self, "警告", "未配置发布平台")
            return
        
        # Get version
        parser = get_parser(project_type)
        version = "0.0.0"
        if parser:
            version_file = os.path.join(path, parser.get_version_file())
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                v = parser.get_version(content)
                if v:
                    version = VersionParser.version_to_string(v)
        
        # Find ZIP file
        archive_path = self.config.get_archive_path() or os.path.dirname(path)
        zip_filename = f"{project_name}_v{version}.zip"
        zip_path = os.path.join(archive_path, zip_filename)
        
        if not os.path.exists(zip_path):
            reply = QMessageBox.question(
                self, "确认",
                f"未找到打包文件: {zip_filename}\n是否先进行打包？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.package_project()
                # Note: User needs to click publish again after packaging
                self.log("⚠️ 打包完成后请再次点击发布")
                return
            else:
                return
        
        self.log(f"🚀 开始发布 {project_name} v{version}...")
        self.publish_btn.setEnabled(False)
        
        # Create and start worker
        self.publish_worker = PublishWorker(
            path, project_name, version, zip_path,
            publish_to, self.current_project, self.config
        )
        self.publish_worker.progress.connect(self.log)
        self.publish_worker.finished.connect(self.on_publish_finished)
        self.publish_worker.start()
    
    def on_publish_finished(self, results: dict):
        """Handle publish completion."""
        self.publish_btn.setEnabled(True)
        self.refresh_project()

    
    def open_sync_dialog(self):
        """Open the git sync management dialog."""
        if not self.current_project:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        
        path = self.current_project.get("path", "")
        dialog = SyncDialog(path, self)
        dialog.exec_()
        self.refresh_project()
    
    def show_project_context_menu(self, pos):
        """Show context menu for project list."""
        item = self.project_list.itemAt(pos)
        if not item:
            return
        
        menu = QMenu(self)
        
        edit_action = QAction("✏️ 编辑设置", self)
        edit_action.triggered.connect(lambda: self.edit_project(item))
        menu.addAction(edit_action)
        
        sync_action = QAction("🔄 同步管理", self)
        sync_action.triggered.connect(lambda: self.open_sync_for_item(item))
        menu.addAction(sync_action)
        
        open_action = QAction("📁 打开目录", self)
        open_action.triggered.connect(lambda: os.startfile(item.project_data.get("path", "")))
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        remove_action = QAction("🗑️ 移除", self)
        remove_action.triggered.connect(lambda: self.remove_project(item))
        menu.addAction(remove_action)
        
        menu.exec_(self.project_list.mapToGlobal(pos))
    
    def open_sync_for_item(self, item: ProjectItem):
        """Open sync dialog for a specific project item."""
        path = item.project_data.get("path", "")
        dialog = SyncDialog(path, self)
        dialog.exec_()
    
    def edit_project(self, item: ProjectItem):
        """Edit a project's settings."""
        dialog = ProjectDialog(self, project_data=item.project_data)
        if dialog.exec_() == QDialog.Accepted and dialog.project_data:
            path = item.project_data.get("path", "")
            self.config.update_project(path, dialog.project_data)
            self.load_projects()
            self.log(f"项目设置已更新: {os.path.basename(path)}")
    
    def remove_project(self, item: ProjectItem):
        """Remove a project from the list."""
        reply = QMessageBox.question(
            self, "确认",
            f"确定要移除项目 {os.path.basename(item.project_data.get('path', ''))} 吗？\n（不会删除实际文件）",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.remove_project(item.project_data.get("path", ""))
            self.load_projects()
            self.log("项目已移除")
    
    def open_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self.config, self)
        dialog.exec_()
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop - add dropped folders as projects."""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                project_type = detect_project_type(path) or "custom"
                project_data = {
                    "path": path,
                    "type": project_type,
                    "publish_to": [],
                    "github_repo": "",
                    "gitee_repo": "",
                    "gitea_repo": ""
                }
                if self.config.add_project(project_data):
                    self.load_projects()
                    self.log(f"添加项目: {path}")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Apply dark theme
    from gui.styles import apply_dark_theme
    apply_dark_theme(app)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
