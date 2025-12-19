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


class ProjectItem(QListWidgetItem):
    """Custom list item for projects."""
    
    STATUS_ICONS = {
        "synced": "✅",
        "modified": "⚠️",
        "ahead": "⬆️",
        "behind": "⬇️",
        "conflict": "❌",
        "unknown": "❓"
    }
    
    def __init__(self, project_data: dict):
        super().__init__()
        self.project_data = project_data
        self.status = "unknown"
        self.update_display()
    
    def update_display(self):
        name = os.path.basename(self.project_data.get("path", "Unknown"))
        icon = self.STATUS_ICONS.get(self.status, "❓")
        self.setText(f"{icon} {name}")
    
    def set_status(self, status: str):
        self.status = status
        self.update_display()


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


class SyncDialog(QDialog):
    """Dialog for git sync operations with per-remote status."""
    
    def __init__(self, project_path: str, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.git = GitHelper(project_path)
        self.setWindowTitle("Git 同步管理")
        self.setMinimumSize(650, 450)
        self.setup_ui()
        self.refresh_status()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"📂 {os.path.basename(self.project_path)}")
        header.setFont(QFont("", 14, QFont.Bold))
        layout.addWidget(header)
        
        # Remotes table
        remotes_group = QGroupBox("远程仓库状态")
        remotes_layout = QVBoxLayout(remotes_group)
        
        self.remotes_table = QListWidget()
        self.remotes_table.setMinimumHeight(150)
        remotes_layout.addWidget(self.remotes_table)
        
        refresh_btn = QPushButton("🔄 刷新状态")
        refresh_btn.clicked.connect(self.refresh_status)
        remotes_layout.addWidget(refresh_btn)
        
        layout.addWidget(remotes_group)
        
        # Actions group
        actions_group = QGroupBox("同步操作")
        actions_layout = QVBoxLayout(actions_group)
        
        # Pull section
        pull_layout = QHBoxLayout()
        self.remote_combo = QComboBox()
        self.remote_combo.setMinimumWidth(150)
        pull_layout.addWidget(QLabel("选择远程:"))
        pull_layout.addWidget(self.remote_combo)
        
        self.pull_btn = QPushButton("⬇️ 拉取 (Pull Rebase)")
        self.pull_btn.clicked.connect(self.do_pull_rebase)
        pull_layout.addWidget(self.pull_btn)
        
        self.force_push_btn = QPushButton("⬆️ 强制推送")
        self.force_push_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        self.force_push_btn.clicked.connect(self.do_force_push)
        pull_layout.addWidget(self.force_push_btn)
        
        pull_layout.addStretch()
        actions_layout.addLayout(pull_layout)
        
        # Push all button
        push_all_layout = QHBoxLayout()
        self.push_all_btn = QPushButton("📤 推送到所有远程")
        self.push_all_btn.clicked.connect(self.do_push_all)
        push_all_layout.addWidget(self.push_all_btn)
        push_all_layout.addStretch()
        actions_layout.addLayout(push_all_layout)
        
        layout.addWidget(actions_group)
        
        # Conflict section
        conflict_group = QGroupBox("冲突处理")
        conflict_layout = QVBoxLayout(conflict_group)
        
        self.conflict_label = QLabel("✅ 无冲突")
        self.conflict_label.setStyleSheet("color: green;")
        conflict_layout.addWidget(self.conflict_label)
        
        conflict_btn_layout = QHBoxLayout()
        
        self.open_vscode_btn = QPushButton("📝 用 VS Code 解决冲突")
        self.open_vscode_btn.clicked.connect(self.open_vscode)
        self.open_vscode_btn.setEnabled(False)
        conflict_btn_layout.addWidget(self.open_vscode_btn)
        
        self.abort_btn = QPushButton("❌ 中止操作")
        self.abort_btn.clicked.connect(self.abort_operation)
        self.abort_btn.setEnabled(False)
        conflict_btn_layout.addWidget(self.abort_btn)
        
        conflict_btn_layout.addStretch()
        conflict_layout.addLayout(conflict_btn_layout)
        
        layout.addWidget(conflict_group)
        
        # Log
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)
        
        # Close button
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def log(self, msg: str):
        self.log_text.append(msg)
    
    def refresh_status(self):
        """Refresh status for all remotes."""
        self.remotes_table.clear()
        self.remote_combo.clear()
        
        remotes = self.git.get_remotes_with_details()
        
        for remote in remotes:
            name = remote.get("name", "")
            platform = remote.get("platform", "unknown")
            
            status = self.git.get_remote_status(name)
            ahead = status.get("ahead", 0)
            behind = status.get("behind", 0)
            
            if status.get("error"):
                status_text = f"❌ {status['error']}"
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
            elif not status.get("error"):
                item.setForeground(QColor("green"))
            else:
                item.setForeground(QColor("red"))
            
            self.remotes_table.addItem(item)
            self.remote_combo.addItem(f"{name} ({platform})", name)
        
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
        """Pull with rebase from selected remote."""
        remote = self.remote_combo.currentData()
        if not remote:
            return
        
        self.log(f"⬇️ 正在从 {remote} 拉取...")
        success, msg = self.git.pull_rebase(remote)
        
        if success:
            self.log(f"✅ {msg}")
        else:
            self.log(f"❌ {msg}")
            if "conflicts" in msg.lower():
                self.log("请使用 VS Code 解决冲突后重试")
        
        self.refresh_status()
    
    def do_force_push(self):
        """Force push to selected remote."""
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
        
        self.log(f"⬆️ 正在强制推送到 {remote}...")
        success, msg = self.git.force_push(remote)
        
        if success:
            self.log(f"✅ {msg}")
        else:
            self.log(f"❌ {msg}")
        
        self.refresh_status()
    
    def do_push_all(self):
        """Push to all remotes."""
        remotes = self.git.get_remotes()
        branch = self.git.get_current_branch() or "main"
        
        self.log("📤 推送到所有远程仓库...")
        
        for remote in remotes:
            name = remote.get("name", "")
            self.log(f"  → {name}...")
            
            if self.git.push(name, branch):
                self.log(f"    ✅ 成功")
            else:
                self.log(f"    ⚠️ 失败 (可能需要先拉取)")
        
        self.refresh_status()
    
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
        
        self.refresh_status()


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
        self.type_combo.addItems(["auto", "blender_addon", "npm", "python", "custom"])
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
    
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.current_project = None
        self.worker = None
        
        self.setWindowTitle("Git Version Manager")
        self.setMinimumSize(900, 600)
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
        
        # Actions
        actions_group = QGroupBox("操作")
        actions_layout = QHBoxLayout(actions_group)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_project)
        actions_layout.addWidget(self.refresh_btn)
        
        self.bump_btn = QPushButton("⬆️ 版本号+1")
        self.bump_btn.clicked.connect(self.bump_version)
        actions_layout.addWidget(self.bump_btn)
        
        self.package_btn = QPushButton("📦 打包")
        self.package_btn.clicked.connect(self.package_project)
        actions_layout.addWidget(self.package_btn)
        
        self.publish_btn = QPushButton("🚀 发布")
        self.publish_btn.clicked.connect(self.publish_project)
        actions_layout.addWidget(self.publish_btn)
        
        self.sync_btn = QPushButton("🔄 同步管理")
        self.sync_btn.clicked.connect(self.open_sync_dialog)
        actions_layout.addWidget(self.sync_btn)
        
        right_layout.addWidget(actions_group)
        
        # Log
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        right_layout.addWidget(log_group)
        
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
        for project in self.config.get_projects():
            item = ProjectItem(project)
            self.project_list.addItem(item)
    
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
        """Handle project selection (no auto-refresh)."""
        self.current_project = item.project_data
        self.update_project_display()
        # Reset version labels until manual refresh
        self.local_version_label.setText("-")
        self.github_version_label.setText("▶ GitHub: -")
        self.gitee_version_label.setText("▶ Gitee: -")
        self.gitea_version_label.setText("▶ Gitea: -")
        self.status_label.setText("点击刷新按钮检查状态")
    
    def update_project_display(self):
        """Update the project info display."""
        if not self.current_project:
            return
        
        path = self.current_project.get("path", "")
        self.name_label.setText(os.path.basename(path))
        self.path_label.setText(path)
        self.type_label.setText(self.current_project.get("type", "unknown"))
    
    def refresh_project(self):
        """Refresh project status."""
        if not self.current_project:
            return
        
        path = self.current_project.get("path", "")
        project_type = self.current_project.get("type", "")
        
        self.log(f"刷新项目: {os.path.basename(path)}")
        
        # Git status
        git = GitHelper(path)
        if not git.is_git_repo():
            self.status_label.setText("❌ 不是Git仓库")
            return
        
        # Get all remotes
        remotes = git.get_remotes_with_details()
        
        # Fetch all remotes
        for remote in remotes:
            git.fetch(remote.get("name", "origin"))
        
        # Check local changes
        has_changes = git.has_local_changes()
        
        # Local version
        parser = get_parser(project_type)
        local_version = None
        if parser:
            version_file = os.path.join(path, parser.get_version_file())
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                local_version = parser.get_version(content)
                if local_version:
                    self.local_version_label.setText(VersionParser.version_to_string(local_version))
        
        # Per-platform remote versions
        platform_status = {}
        for remote in remotes:
            remote_name = remote.get("name", "")
            platform = remote.get("platform", "")
            
            if not platform:
                continue
            
            # Skip if we already have a successful status for this platform
            if platform in platform_status and platform_status[platform][1] != "gray":
                continue
            
            # Get remote version
            remote_content = git.get_remote_file_content(
                parser.get_version_file() if parser else "__init__.py",
                remote=remote_name
            )
            
            if remote_content and parser:
                remote_version = parser.get_version(remote_content)
                if remote_version:
                    version_str = VersionParser.version_to_string(remote_version)
                    
                    # Compare with local
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
                else:
                    # Only set failure status if no existing status
                    if platform not in platform_status:
                        platform_status[platform] = ("无法解析", "gray")
            else:
                # Only set failure status if no existing status
                if platform not in platform_status:
                    platform_status[platform] = ("无远程数据", "gray")
        
        # Update UI labels
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
        ahead, behind = git.is_ahead_of_remote()
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
        
        # Update list item status
        current_item = self.project_list.currentItem()
        if isinstance(current_item, ProjectItem):
            if has_changes:
                current_item.set_status("modified")
            elif ahead > 0:
                current_item.set_status("ahead")
            elif behind > 0:
                current_item.set_status("behind")
            else:
                current_item.set_status("synced")
    
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
        """Package the project as ZIP."""
        if not self.current_project:
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
        
        # Package
        archive_path = self.config.get_archive_path() or os.path.dirname(path)
        packager = Packager(path, project_name, archive_path)
        
        try:
            zip_path = packager.create_zip(version)
            self.log(f"✅ 打包完成: {zip_path}")
        except Exception as e:
            self.log(f"❌ 打包失败: {e}")
    
    def publish_project(self):
        """Publish project to configured platforms."""
        if not self.current_project:
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
        
        tag = f"v{version}"
        
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
            else:
                return
        
        # Push to all remotes first
        git = GitHelper(path)
        if git.is_git_repo():
            self.log("📤 推送代码到所有远程仓库...")
            remotes = git.get_remotes_with_details()
            
            # Create tag if not exists
            self.log(f"🏷️ 创建标签: {tag}")
            git.create_tag(tag, f"Release {tag}")
            
            # Push to each remote
            for remote in remotes:
                remote_name = remote.get("name", "")
                platform = remote.get("platform", "unknown")
                
                if remote_name:
                    self.log(f"  → 推送到 {platform} ({remote_name})...")
                    
                    # Push branch
                    branch = git.get_current_branch() or "main"
                    if git.push(remote_name, branch):
                        self.log(f"    ✅ 分支推送成功")
                    else:
                        self.log(f"    ⚠️ 分支推送失败")
                    
                    # Push tags
                    if git.push_tags(remote_name):
                        self.log(f"    ✅ 标签推送成功")
                    else:
                        self.log(f"    ⚠️ 标签推送失败")
        
        # Publish releases to each platform
        self.log("📦 发布 Release...")
        for platform in publish_to:
            token = self.config.get_token(platform)
            if not token:
                self.log(f"⚠️ {platform}: 未配置Token")
                continue
            
            repo_key = f"{platform}_repo"
            repo = self.current_project.get(repo_key, "")
            if not repo:
                self.log(f"⚠️ {platform}: 未配置仓库")
                continue
            
            publisher = get_publisher(
                platform, token,
                url=self.config.get_gitea_url() if platform == "gitea" else ""
            )
            
            if publisher:
                self.log(f"🚀 发布到 {platform}: {repo}")
                result = publisher.publish(
                    repo=repo,
                    tag=tag,
                    name=f"{project_name} {tag}",
                    body=f"Release {tag}",
                    asset_path=zip_path
                )
                
                if result.get("success"):
                    self.log(f"✅ {platform}: {result.get('message')}")
                else:
                    self.log(f"❌ {platform}: {result.get('message')}")
    
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
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
