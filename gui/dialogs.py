"""
Git Version Manager - Dialog Windows
Settings, Sync, and Project dialogs

Uses Services layer for business logic.
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QCheckBox, QGroupBox, QTabWidget,
    QListWidget, QListWidgetItem, QFormLayout, QDialogButtonBox,
    QFileDialog, QMessageBox, QInputDialog, QMenu, QAction, QStyle
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

# Services layer for business logic
from services import ProjectService, VersionService, PublishService

# Core modules (only used where services don't cover low-level operations)
from core.git_helper import GitHelper
from core.config_manager import ConfigManager

# GUI workers for async operations
from gui.workers import (
    SyncStatusWorker, SyncOperationWorker, BuildWorker, PackageWorker, PublishWorker
)


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
        self.sync_worker = None
        self.operation_worker = None
        self.setWindowTitle("Git 同步管理")
        self.setMinimumSize(650, 450)
        self.setup_ui()
        # Start async status check after dialog shows
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
        
        # === Tab 1: 状态与同步 (合并原状态+同步+冲突) ===
        status_sync_tab = QWidget()
        status_sync_layout = QVBoxLayout(status_sync_tab)
        
        # Remote status section
        remote_group = QGroupBox("远程仓库状态")
        remote_group_layout = QVBoxLayout(remote_group)
        
        self.remotes_table = QListWidget()
        self.remotes_table.setMinimumHeight(100)
        self.remotes_table.setMaximumHeight(120)
        remote_group_layout.addWidget(self.remotes_table)
        status_sync_layout.addWidget(remote_group)
        
        # Local changes section (新增)
        changes_group = QGroupBox("本地变更")
        changes_group_layout = QVBoxLayout(changes_group)
        
        self.changed_files_list = QListWidget()
        self.changed_files_list.setMinimumHeight(80)
        self.changed_files_list.setMaximumHeight(120)
        self.changed_files_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.changed_files_list.customContextMenuRequested.connect(self.show_file_context_menu)
        changes_group_layout.addWidget(self.changed_files_list)
        status_sync_layout.addWidget(changes_group)
        
        # Sync operation buttons
        sync_btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_status_async)
        sync_btn_layout.addWidget(self.refresh_btn)
        
        # Remote selector
        sync_btn_layout.addWidget(QLabel("远程:"))
        self.remote_combo = QComboBox()
        self.remote_combo.setMinimumWidth(120)
        sync_btn_layout.addWidget(self.remote_combo)
        
        self.pull_btn = QPushButton("⬇️ 拉取")
        self.pull_btn.clicked.connect(self.do_pull_rebase)
        sync_btn_layout.addWidget(self.pull_btn)
        
        self.push_all_btn = QPushButton("📤 推送所有")
        self.push_all_btn.clicked.connect(self.do_push_all)
        sync_btn_layout.addWidget(self.push_all_btn)
        
        status_sync_layout.addLayout(sync_btn_layout)
        
        # Conflict section (条件显示)
        self.conflict_group = QGroupBox("⚠️ 冲突处理")
        conflict_group_layout = QHBoxLayout(self.conflict_group)
        
        self.conflict_label = QLabel("检查中...")
        conflict_group_layout.addWidget(self.conflict_label)
        
        self.open_vscode_btn = QPushButton("📝 VS Code")
        self.open_vscode_btn.clicked.connect(self.open_vscode)
        self.open_vscode_btn.setEnabled(False)
        conflict_group_layout.addWidget(self.open_vscode_btn)
        
        self.abort_btn = QPushButton("❌ 中止")
        self.abort_btn.clicked.connect(self.abort_operation)
        self.abort_btn.setEnabled(False)
        conflict_group_layout.addWidget(self.abort_btn)
        
        self.conflict_group.setVisible(False)  # 默认隐藏
        status_sync_layout.addWidget(self.conflict_group)
        
        self.tabs.addTab(status_sync_tab, "📊 状态与同步")
        
        # === Tab 2: 提交发布 (合并原提交+打包发布+版本升级) ===
        commit_publish_tab = QWidget()
        commit_publish_layout = QVBoxLayout(commit_publish_tab)
        
        # Version section (从主窗口移入)
        version_group = QGroupBox("版本管理")
        version_group_layout = QHBoxLayout(version_group)
        
        version_group_layout.addWidget(QLabel("当前版本:"))
        self.version_label = QLabel("-")
        self.version_label.setStyleSheet("font-weight: bold;")
        version_group_layout.addWidget(self.version_label)
        version_group_layout.addStretch()
        
        self.bump_btn = QPushButton("⬆️ 版本+1")
        self.bump_btn.clicked.connect(self.do_bump_version)
        version_group_layout.addWidget(self.bump_btn)
        
        commit_publish_layout.addWidget(version_group)
        
        # Commit section
        commit_group = QGroupBox("提交更改")
        commit_group_layout = QVBoxLayout(commit_group)
        
        commit_group_layout.addWidget(QLabel("更新日志:"))
        self.changelog_input = QTextEdit()
        self.changelog_input.setPlaceholderText("请输入本次提交的更新内容...")
        self.changelog_input.setMaximumHeight(100)
        commit_group_layout.addWidget(self.changelog_input)
        
        self.commit_push_btn = QPushButton("💾 提交并推送到所有远程")
        self.commit_push_btn.setStyleSheet("background-color: #4dabf5; color: white; padding: 8px;")
        self.commit_push_btn.clicked.connect(self.do_commit_and_push_all)
        commit_group_layout.addWidget(self.commit_push_btn)
        
        commit_publish_layout.addWidget(commit_group)
        
        # Package & Publish section
        publish_group = QGroupBox("打包与发布")
        publish_group_layout = QHBoxLayout(publish_group)
        
        self.package_btn = QPushButton("📦 创建 ZIP 包")
        self.package_btn.clicked.connect(self.do_package)
        publish_group_layout.addWidget(self.package_btn)
        
        self.publish_btn = QPushButton("🚀 发布版本")
        self.publish_btn.setStyleSheet("background-color: #51cf66; color: white;")
        self.publish_btn.clicked.connect(self.do_publish)
        publish_group_layout.addWidget(self.publish_btn)
        
        commit_publish_layout.addWidget(publish_group)
        commit_publish_layout.addStretch()
        
        self.tabs.addTab(commit_publish_tab, "💾 提交发布")
        
        # === Tab 3: 高级操作 ===
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        
        # Build section (only for python_app)
        self.build_section = QGroupBox("🔨 编译项目")
        build_section_layout = QVBoxLayout(self.build_section)
        self.build_btn = QPushButton("🔨 编译项目 (执行 .bat)")
        self.build_btn.clicked.connect(self.do_build)
        build_section_layout.addWidget(self.build_btn)
        advanced_layout.addWidget(self.build_section)
        
        # Danger zone
        danger_group = QGroupBox("⚠️ 危险操作")
        danger_group.setStyleSheet("QGroupBox { color: #ff6b6b; }")
        danger_group_layout = QVBoxLayout(danger_group)
        
        danger_group_layout.addWidget(QLabel("以下操作可能导致数据丢失，请谨慎使用"))
        
        force_push_layout = QHBoxLayout()
        force_push_layout.addWidget(QLabel("选择远程:"))
        self.force_remote_combo = QComboBox()
        self.force_remote_combo.setMinimumWidth(150)
        force_push_layout.addWidget(self.force_remote_combo)
        
        self.force_push_btn = QPushButton("⬆️ 强制推送")
        self.force_push_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        self.force_push_btn.clicked.connect(self.do_force_push)
        force_push_layout.addWidget(self.force_push_btn)
        force_push_layout.addStretch()
        
        danger_group_layout.addLayout(force_push_layout)
        advanced_layout.addWidget(danger_group)
        
        advanced_layout.addStretch()
        self.tabs.addTab(advanced_tab, "🔧 高级操作")
        
        # Show/hide build section based on project type
        self.update_build_section_visibility()
        
        # Log (always visible at bottom, stretches with window)
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(60)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group, 1)  # stretch factor 1
        
        # Close button
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        # Ensure all operation buttons are enabled initially
        self.set_operation_buttons_enabled(True)
        
        # Initialize version display
        self.refresh_version_display()
    
    def showEvent(self, event):
        """Handle dialog show event."""
        super().showEvent(event)
        # Ensure buttons are enabled when dialog is shown
        self.set_operation_buttons_enabled(True)
        # Update build section visibility
        self.update_build_section_visibility()
    
    def log(self, msg: str):
        self.log_text.append(msg)
    
    def update_build_section_visibility(self):
        """Show/hide build section based on project type."""
        main_window = self.parent()
        if main_window and hasattr(main_window, 'current_project') and main_window.current_project:
            project_type = main_window.current_project.get("type", "")
            self.build_section.setVisible(project_type == "python_app")
        else:
            self.build_section.setVisible(False)
    
    def set_operation_buttons_enabled(self, enabled: bool):
        """Enable/disable all operation buttons."""
        self.pull_btn.setEnabled(enabled)
        self.force_push_btn.setEnabled(enabled)
        self.push_all_btn.setEnabled(enabled)
        self.commit_push_btn.setEnabled(enabled)
        self.build_btn.setEnabled(enabled)
        self.package_btn.setEnabled(enabled)
        self.publish_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
        self.bump_btn.setEnabled(enabled)
    
    def refresh_status_async(self):
        """Refresh status for all remotes asynchronously."""
        if self.sync_worker and self.sync_worker.isRunning():
            self.log("⏳ 正在检查中，请稍候...")
            return
        
        self.remotes_table.clear()
        self.remote_combo.clear()
        self.force_remote_combo.clear()
        self.refresh_btn.setEnabled(False)
        self.log("🔄 开始检查远程状态...")
        
        # Refresh changed files list
        self.refresh_changed_files()
        
        # Refresh version display
        self.refresh_version_display()
        
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
        self.force_remote_combo.addItem(f"{name} ({platform})", name)
    
    def on_status_check_finished(self):
        """Handle status check completion."""
        self.refresh_btn.setEnabled(True)
        # Ensure operation buttons are enabled after status check
        self.set_operation_buttons_enabled(True)
        self.check_conflicts()
    
    def check_conflicts(self):
        """Check and display conflict status."""
        if self.git.has_merge_conflicts():
            conflicts = self.git.get_conflict_files()
            self.conflict_label.setText(f"⚠️ 检测到 {len(conflicts)} 个冲突文件")
            self.conflict_label.setStyleSheet("color: red; font-weight: bold;")
            self.open_vscode_btn.setEnabled(True)
            self.abort_btn.setEnabled(True)
            self.conflict_group.setVisible(True)
        else:
            self.conflict_label.setText("✅ 无冲突")
            self.conflict_label.setStyleSheet("color: green;")
            self.open_vscode_btn.setEnabled(False)
            self.abort_btn.setEnabled(False)
            self.conflict_group.setVisible(False)
    
    def refresh_changed_files(self):
        """Refresh the list of changed files."""
        self.changed_files_list.clear()
        
        changed_files = self.git.get_changed_files_with_status()
        
        for file_info in changed_files:
            status = file_info["status"]
            path = file_info["path"]
            
            # Format display text
            status_icons = {
                "M": "📝",   # Modified
                "A": "➕",   # Added  
                "D": "❌",   # Deleted
                "R": "📛",   # Renamed
                "??": "❓",  # Untracked
            }
            icon = status_icons.get(status, "📄")
            item = QListWidgetItem(f"{icon} [{status}] {path}")
            item.setData(Qt.UserRole, path)  # Store full path for revert
            
            # Set color based on status
            if status == "M":
                item.setForeground(QColor("orange"))
            elif status == "A":
                item.setForeground(QColor("green"))
            elif status == "D":
                item.setForeground(QColor("red"))
            elif status == "??":
                item.setForeground(QColor("gray"))
            
            self.changed_files_list.addItem(item)
        
        if not changed_files:
            item = QListWidgetItem("✅ 没有未提交的更改")
            item.setForeground(QColor("green"))
            self.changed_files_list.addItem(item)
    
    def show_file_context_menu(self, pos):
        """Show context menu for file list."""
        item = self.changed_files_list.itemAt(pos)
        if not item:
            return
        
        file_path = item.data(Qt.UserRole)
        if not file_path:
            return
        
        menu = QMenu(self)
        
        revert_action = QAction("↩️ 还原此文件", self)
        revert_action.triggered.connect(lambda: self.revert_file(item))
        menu.addAction(revert_action)
        
        open_action = QAction("📂 在资源管理器中打开", self)
        open_action.triggered.connect(lambda: self.open_file_location(file_path))
        menu.addAction(open_action)
        
        menu.exec_(self.changed_files_list.mapToGlobal(pos))
    
    def revert_file(self, item):
        """Revert the selected file."""
        file_path = item.data(Qt.UserRole)
        if not file_path:
            return
        
        reply = QMessageBox.warning(
            self, "确认还原",
            f"确定要还原文件 '{os.path.basename(file_path)}' 吗？\n\n"
            "此操作将丢弃所有未提交的修改，且无法恢复！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, msg = self.git.revert_file(file_path)
            if success:
                self.log(f"✅ {msg}")
                self.refresh_changed_files()
            else:
                self.log(f"❌ {msg}")
    
    def open_file_location(self, file_path: str):
        """Open file location in explorer."""
        import subprocess
        full_path = os.path.join(self.project_path, file_path)
        if os.path.exists(full_path):
            subprocess.Popen(f'explorer /select,"{full_path}"', shell=True)
        else:
            # File might be deleted, open parent directory
            parent_dir = os.path.dirname(full_path)
            if os.path.exists(parent_dir):
                subprocess.Popen(f'explorer "{parent_dir}"', shell=True)
    
    def refresh_version_display(self):
        """Refresh the version display label."""
        main_window = self.parent()
        if main_window and hasattr(main_window, 'current_project') and main_window.current_project:
            path = main_window.current_project.get("path", "")
            project_type = main_window.current_project.get("type", "")
            
            version_service = VersionService()
            version = version_service.get_version_string(path, project_type)
            
            if version:
                self.version_label.setText(f"v{version}")
            else:
                self.version_label.setText("未检测到版本")
        else:
            self.version_label.setText("-")
    
    def do_bump_version(self):
        """Bump the patch version."""
        main_window = self.parent()
        if not main_window or not hasattr(main_window, 'current_project') or not main_window.current_project:
            self.log("❌ 无法访问项目信息")
            return
        
        path = main_window.current_project.get("path", "")
        project_type = main_window.current_project.get("type", "")
        
        version_service = VersionService()
        result = version_service.bump_version(path, project_type, "patch")
        
        if result["success"]:
            self.log(f"✅ {result['message']}")
            self.refresh_version_display()
            self.refresh_changed_files()
        else:
            self.log(f"❌ {result['message']}")
    
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
        remote = self.force_remote_combo.currentData()
        if not remote:
            self.log("⚠️ 请先在高级操作页面选择远程仓库")
            return
        
        # Step 1: Warning dialog
        reply = QMessageBox.warning(
            self, "⚠️ 危险操作",
            f"强制推送将覆盖远程 {remote} 上的更改！\n\n"
            "这可能导致他人的提交丢失，且无法恢复。\n"
            "确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Step 2: Require typing remote name to confirm
        confirm_text, ok = QInputDialog.getText(
            self, "🔒 二次确认",
            f"请输入远程仓库名称 \"{remote}\" 以确认强制推送：",
            QLineEdit.Normal, ""
        )
        
        if not ok or confirm_text.strip() != remote:
            self.log("⚠️ 强制推送已取消 (确认名称不匹配)")
            return
        
        if self.operation_worker and self.operation_worker.isRunning():
            self.log("⏳ 操作正在进行中...")
            return
        
        self.set_operation_buttons_enabled(False)
        self.log(f"⚠️ 正在强制推送到 {remote}...")
        
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
    
    def do_build(self):
        """Build the project (execute build script for python_app)."""
        main_window = self.parent()
        if not main_window or not hasattr(main_window, 'current_project') or not main_window.current_project:
            self.log("❌ 无法访问项目信息")
            return
        
        current_project = main_window.current_project
        path = current_project.get("path", "")
        project_type = current_project.get("type", "")
        
        if project_type != "python_app":
            self.log("❌ 只有 python_app 类型需要编译")
            return
        
        # Prompt user for build script
        default_dir = path
        if os.path.exists(os.path.join(path, "build.bat")):
            default_dir = os.path.join(path, "build.bat")
        
        build_script, _ = QFileDialog.getOpenFileName(
            self, "选择构建脚本 (.bat)", default_dir, "Batch Files (*.bat);;All Files (*)"
        )
        
        if not build_script:
            self.log("⚠️ 已取消编译 (未选择构建脚本)")
            return
        
        self.log(f"🔨 开始编译项目...")
        self.set_operation_buttons_enabled(False)
        
        # Create and start build worker
        self.build_worker = BuildWorker(build_script)
        self.build_worker.progress.connect(self.log)
        self.build_worker.finished.connect(self.on_build_finished)
        self.build_worker.start()
    
    def on_build_finished(self, success: bool, result: str):
        """Handle build completion in sync dialog."""
        self.set_operation_buttons_enabled(True)
        if success:
            self.log(f"✅ 编译成功，可以执行打包了")
        else:
            self.log(f"❌ 编译失败: {result}")
    
    def do_package(self):
        """Package the project as ZIP using VersionService."""
        main_window = self.parent()
        if not main_window or not hasattr(main_window, 'current_project') or not main_window.current_project:
            self.log("❌ 无法访问项目信息")
            return
        
        current_project = main_window.current_project
        path = current_project.get("path", "")
        project_name = os.path.basename(path)
        project_type = current_project.get("type", "")
        
        # Use VersionService to get version
        version_service = VersionService()
        version = version_service.get_version_string(path, project_type)
        
        archive_path = main_window.config.get_archive_path() or os.path.dirname(path)
        
        self.log(f"📦 开始打包 {project_name}...")
        self.set_operation_buttons_enabled(False)
        
        # Create and start worker, connect to THIS dialog's log
        self.package_worker = PackageWorker(path, project_name, archive_path, version, project_type)
        self.package_worker.progress.connect(self.log)  # Connect to dialog's log
        self.package_worker.finished.connect(self.on_package_finished)
        self.package_worker.start()
    
    def on_package_finished(self, success: bool, result: str):
        """Handle package completion in sync dialog."""
        self.set_operation_buttons_enabled(True)
        if success:
            self.log(f"✅ 打包成功: {result}")
        else:
            self.log(f"❌ 打包失败: {result}")
    
    def do_publish(self):
        """Publish project to configured platforms using services."""
        main_window = self.parent()
        if not main_window or not hasattr(main_window, 'current_project') or not main_window.current_project:
            self.log("❌ 无法访问项目信息")
            return
        
        current_project = main_window.current_project
        path = current_project.get("path", "")
        project_name = os.path.basename(path)
        project_type = current_project.get("type", "")
        publish_to = current_project.get("publish_to", [])
        
        if not publish_to:
            self.log("❌ 未配置发布平台")
            QMessageBox.warning(self, "警告", "未配置发布平台")
            return
        
        # Use VersionService to get version
        version_service = VersionService()
        version = version_service.get_version_string(path, project_type)
        
        # Use PublishService to find ZIP
        publish_service = PublishService(main_window.config)
        zip_path = publish_service.get_zip_path(current_project)
        
        if not zip_path:
            archive_path = main_window.config.get_archive_path() or os.path.dirname(path)
            zip_filename = f"{project_name}_v{version}.zip"
            self.log(f"❌ 未找到打包文件: {zip_filename}")
            reply = QMessageBox.question(
                self, "确认",
                f"未找到打包文件: {zip_filename}\n是否先进行打包？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.do_package()
                self.log("⚠️ 打包完成后请再次点击发布")
                return
            else:
                return
        
        self.log(f"✅ 找到打包文件: {os.path.basename(zip_path)}")
        self.log(f"🚀 开始发布 {project_name} v{version}...")
        self.log(f"  发布平台: {', '.join(publish_to)}")
        self.set_operation_buttons_enabled(False)
        
        # Create and start publish worker, connect to THIS dialog's log
        self.publish_worker = PublishWorker(
            path, project_name, version, zip_path,
            publish_to, current_project, main_window.config
        )
        self.publish_worker.progress.connect(self.log)  # Connect to dialog's log
        self.publish_worker.finished.connect(self.on_publish_finished)
        self.publish_worker.start()
    
    def on_publish_finished(self, results: dict):
        """Handle publish completion in sync dialog."""
        self.set_operation_buttons_enabled(True)
        # Show summary
        success_count = sum(1 for r in results.values() if r.get("success"))
        total_count = len(results)
        self.log(f"📊 发布完成: {success_count}/{total_count} 个平台成功")
        
        # Optionally refresh status
        self.refresh_status_async()
    
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
        
        # Get Gitea URL from ConfigManager if not provided
        if gitea_base_url:
            self.gitea_base_url = gitea_base_url
        else:
            config = ConfigManager()
            self.gitea_base_url = config.get_gitea_url() or ""
        
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
        self.type_combo.addItems(["auto", "blender_addon", "python_app", "npm", "python", "ue_plugin", "ue_project", "custom"])
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
            if self.gitea_base_url:
                base = self.gitea_base_url.rstrip('/')
                url = f"{base}/{repo}.git" if repo else f"{base}/..."
            else:
                url = "请先在设置中配置 Gitea URL" if not repo else f"[Gitea URL 未配置]/{repo}.git"
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
            # Auto-detect type using ProjectService
            project_service = ProjectService(ConfigManager())
            detected = project_service.detect_project_type(path)
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
            project_service = ProjectService(ConfigManager())
            project_type = project_service.detect_project_type(path) or "custom"
        
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
            if self.gitea_base_url:
                base = self.gitea_base_url.rstrip('/')
                new_remotes["gitea"] = f"{base}/{gitea_repo}.git"
            # Skip if no Gitea URL configured
        
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
