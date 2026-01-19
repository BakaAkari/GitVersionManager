# Git Version Manager - 系统架构文档

> 一体化的跨平台 Git 项目版本管理与发布工具。

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 目录结构](#2-目录结构)
- [3. 架构分层](#3-架构分层)
- [4. Core 层详解](#4-core-层详解)
- [5. Services 层详解](#5-services-层详解)
- [6. Interfaces 层详解](#6-interfaces-层详解)
- [7. GUI 层详解](#7-gui-层详解)
- [8. 数据流](#8-数据流)
- [9. 扩展指南](#9-扩展指南)

---

## 1. 项目概述

Git Version Manager 是一款使用 Python + PyQt5 开发的桌面应用程序，旨在简化多项目的版本管理和发布流程。

**核心功能:**

- 管理多个本地 Git 项目
- 自动检测并解析多种项目类型的版本号
- 一键打包项目为 ZIP 文件
- 发布 Release 到 GitHub / Gitee / Gitea
- 可视化 Git 同步状态（未提交修改、领先/落后提交数）
- 支持多远程仓库管理

---

## 2. 目录结构

```
GitVersionManager/
├── main.py                    # 程序入口
├── version.txt                # 本应用版本号
├── requirements.txt           # Python 依赖
│
├── interfaces/                # 📌 接口抽象层 (NEW)
│   ├── __init__.py
│   ├── publisher_interface.py # IPublisher + PublisherRegistry
│   └── parser_interface.py    # IVersionParser + ParserRegistry
│
├── services/                  # 📌 业务逻辑服务层 (NEW)
│   ├── __init__.py
│   ├── project_service.py     # 项目管理服务
│   ├── version_service.py     # 版本管理服务
│   └── publish_service.py     # 发布工作流服务
│
├── core/                      # 核心功能模块
│   ├── __init__.py
│   ├── config_manager.py      # 配置文件管理
│   ├── git_helper.py          # Git 操作封装
│   ├── version_parser.py      # 版本号解析器
│   ├── packager.py            # 项目打包
│   └── publisher.py           # Release 发布
│
├── gui/                       # PyQt5 GUI 模块
│   ├── __init__.py
│   ├── main_window.py         # 主窗口
│   ├── dialogs.py             # 对话框 (Settings, Sync, Project)
│   ├── workers.py             # Worker 线程类
│   ├── widgets.py             # 自定义控件
│   ├── styles.py              # 暗色主题样式表
│   └── icon_utils.py          # 动态图标生成
│
├── resources/                 # 资源文件
│   └── icon.ico
│
└── Docs/
    └── SystemArchitecture.md  # 本文档
```

---

## 3. 架构分层

```
┌─────────────────────────────────────────────────────────────────┐
│                          GUI 层                                  │
│    main_window.py  │  dialogs.py  │  workers.py  │  widgets.py  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ 调用
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Services 层                                │
│    ProjectService    │    VersionService    │    PublishService │
└─────────────────────────────┬───────────────────────────────────┘
                              │ 调用
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Interfaces 层                               │
│       IPublisher  │  PublisherRegistry                          │
│       IVersionParser  │  ParserRegistry                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ 调用
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Core 层                                  │
│   config_manager  │  git_helper  │  packager  │  publisher      │
│                        version_parser                            │
└─────────────────────────────────────────────────────────────────┘
```

**设计原则:**

- **GUI 层** 只调用 Services 层，不直接访问 Core
- **Services 层** 封装业务逻辑，是 GUI 与 Core 之间的桥梁
- **Interfaces 层** 提供可扩展的接口抽象和注册表
- **Core 层** 提供底层功能实现

---

## 4. Core 层详解

### 4.1 config_manager.py

配置文件的读取、写入与管理。

```python
class ConfigManager:
    def get_archive_path() -> str
    def set_archive_path(path: str)
    def get_token(platform: str) -> str
    def set_token(platform: str, token: str, url: str = "")
    def get_projects() -> List[dict]
    def add_project(project: dict) -> bool
    def update_project(path: str, updates: dict)
    def remove_project(path: str) -> bool
```

### 4.2 git_helper.py

Git 命令行操作封装。

```python
class GitHelper:
    def is_git_repo() -> bool
    def has_local_changes() -> bool
    def get_remotes_with_details() -> List[dict]
    def fetch(remote) -> bool
    def commit(message, add_all) -> bool
    def push(remote, branch) -> bool
    def pull_rebase(remote, branch) -> Tuple[bool, str]
    def create_tag(tag_name, message) -> bool
    def push_tags(remote) -> bool
```

### 4.3 version_parser.py

版本号解析器 (策略模式)。

**支持的项目类型:**

| 类型 | 版本文件 | 版本格式 |
|------|----------|----------|
| `blender_addon` | `__init__.py` | `"version": (1, 2, 3)` |
| `npm` | `package.json` | `"version": "1.2.3"` |
| `python` | `pyproject.toml` | `version = "1.2.3"` |
| `python_app` | `version.txt` | `1.2.3` |
| `ue_plugin` | `*.uplugin` | `"VersionName": "1.2.3"` |
| `ue_project` | `*.uproject` | Git 状态追踪 |

### 4.4 packager.py

项目打包为 ZIP 文件。

```python
class Packager:
    def create_zip(version) -> str
    def create_dist_zip(version) -> str  # python_app 专用
```

### 4.5 publisher.py

发布 Release 到 Git 平台 (策略模式)。

```python
class ReleasePublisher:
    platform_name: str  # 用于注册表
    def publish(repo, tag, name, body, asset_path) -> dict
```

**已实现:** GitHubPublisher, GiteePublisher, GiteaPublisher

---

## 5. Services 层详解

### 5.1 ProjectService

项目管理业务逻辑。

```python
class ProjectService:
    def __init__(config: ConfigManager)
    
    def get_all_projects() -> List[dict]
    def add_project(project: dict) -> bool
    def update_project(path: str, updates: dict) -> bool
    def remove_project(path: str) -> bool
    def detect_project_type(path: str) -> Optional[str]
    def get_project_status(project: dict) -> dict
    def open_in_explorer(path: str) -> bool
```

### 5.2 VersionService

版本管理业务逻辑。

```python
class VersionService:
    def get_version_info(project_path, project_type) -> dict
    def get_version(project_path, project_type) -> Optional[Tuple]
    def get_version_string(project_path, project_type) -> str
    def bump_version(project_path, project_type, bump_type) -> dict
    def create_version_file(project_path, project_type) -> dict
    
    # Utility methods
    @staticmethod
    def version_to_string(version: Tuple) -> str
    def parse_version_from_content(content, project_type) -> Optional[Tuple]
```

### 5.3 PublishService

发布工作流业务逻辑。

```python
class PublishService:
    def __init__(config: ConfigManager)
    
    def get_project_version(project: dict) -> str
    def get_zip_path(project: dict) -> Optional[str]
    def package_project(project, progress_callback) -> dict
    def commit_and_push_all(project, message, progress_callback) -> dict
    def publish_to_platforms(project, zip_path, progress_callback) -> Dict
    def full_publish_workflow(project, commit_message, progress_callback) -> dict
```

---

## 6. Interfaces 层详解

### 6.1 IPublisher 接口

```python
class IPublisher(ABC):
    platform_name: str
    
    @abstractmethod
    def __init__(token: str, **kwargs): ...
    
    @abstractmethod
    def publish(repo, tag, name, body, asset_path) -> Dict: ...
    
    def validate_config(repo, token) -> Dict: ...
```

### 6.2 PublisherRegistry

```python
class PublisherRegistry:
    @classmethod
    def register(publisher_class: Type[IPublisher]): ...
    
    @classmethod
    def get(platform: str, token: str, **kwargs) -> Optional[IPublisher]: ...
    
    @classmethod
    def get_available() -> list: ...
```

**使用示例:**
```python
# 注册自定义发布器
from interfaces import PublisherRegistry

class MyPublisher(IPublisher):
    platform_name = "my_platform"
    # ...

PublisherRegistry.register(MyPublisher)

# 获取发布器
publisher = PublisherRegistry.get("my_platform", token="xxx")
```

### 6.3 IVersionParser 接口

```python
class IVersionParser(ABC):
    project_type: str
    version_file: str
    
    @abstractmethod
    def get_version(content: str) -> Optional[Tuple]: ...
    
    @abstractmethod
    def set_version(content: str, version: Tuple) -> str: ...
```

### 6.4 ParserRegistry

```python
class ParserRegistry:
    @classmethod
    def register(parser_class: Type[IVersionParser]): ...
    
    @classmethod
    def get(project_type: str, project_path: str = None) -> Optional[IVersionParser]: ...
    
    @classmethod
    def detect(project_path: str) -> Optional[IVersionParser]: ...
```

---

## 7. GUI 层详解

### 7.1 main_window.py

主窗口，使用 Services 层处理所有业务逻辑。

```python
class MainWindow(QMainWindow):
    def __init__(self):
        self.config = ConfigManager()
        self.project_service = ProjectService(self.config)
        self.version_service = VersionService()
        self.publish_service = PublishService(self.config)
```

### 7.2 dialogs.py

对话框模块。

| 类名 | 职责 |
|------|------|
| `SettingsDialog` | 应用设置 |
| `SyncDialog` | Git 同步管理 (5个Tab) |
| `ProjectDialog` | 添加/编辑项目 |

### 7.3 workers.py

Worker 线程类，使用 VersionService 获取版本信息。

| 类名 | 功能 |
|------|------|
| `RefreshWorker` | 刷新项目状态 |
| `ProjectStatusWorker` | 启动时并行检查 |
| `SyncStatusWorker` | 检查远程同步状态 |
| `SyncOperationWorker` | Git 操作 |
| `BuildWorker` | 执行构建脚本 |
| `PackageWorker` | 打包操作 |
| `PublishWorker` | 发布操作 |

### 7.4 widgets.py

自定义控件。

```python
class ProjectItem(QListWidgetItem):
    def set_status(status: str, local_version: str = "")
    def set_cached_status(platform_status, has_changes, ahead, behind, changed_files)
```

---

## 8. 数据流

### 8.1 启动流程

```
main.py
  └─▶ MainWindow.__init__()
        ├─▶ ProjectService(config)
        ├─▶ VersionService()
        ├─▶ PublishService(config)
        └─▶ load_projects()
              └─▶ project_service.get_all_projects()
```

### 8.2 刷新项目状态

```
[刷新] 按钮
  └─▶ RefreshWorker.run()
        ├─▶ GitHelper 操作
        ├─▶ VersionService.get_version_info()
        └─▶ emit finished(result)
              └─▶ on_refresh_finished()
                    └─▶ version_service.version_to_string()
```

### 8.3 版本升级

```
[版本+1] 按钮
  └─▶ bump_version()
        └─▶ version_service.bump_version(path, type, "patch")
              ├─▶ 读取版本文件
              ├─▶ VersionParser.bump_patch()
              └─▶ 写入新版本
```

### 8.4 发布流程

```
[发布] 按钮
  └─▶ PublishWorker.run()
        ├─▶ GitHelper.push() × N
        ├─▶ GitHelper.push_tags() × N
        └─▶ PublisherRegistry.get() → publish()
```

---

## 9. 扩展指南

### 9.1 添加新项目类型

**Step 1: 创建解析器**

```python
# core/version_parser.py
class UnityParser(VersionParser):
    def get_version_file(self) -> str:
        return "ProjectSettings/ProjectSettings.asset"
    
    def get_version(self, content: str) -> Optional[Tuple]:
        # 实现版本解析
        pass
    
    def set_version(self, content: str, version: Tuple) -> str:
        # 实现版本设置
        pass
```

**Step 2: 注册到工厂**

```python
def get_parser(project_type: str, **kwargs):
    parsers = {
        # ...
        "unity": UnityParser,
    }
```

### 9.2 添加新发布平台

**Step 1: 创建发布器**

```python
# core/publisher.py
class GitLabPublisher(ReleasePublisher):
    platform_name = "gitlab"
    
    def __init__(self, token: str, **kwargs):
        super().__init__(token, **kwargs)
        self.base_url = kwargs.get("url", "https://gitlab.com")
    
    def publish(self, repo, tag, name, body, asset_path) -> dict:
        # 实现发布逻辑
        pass
```

**Step 2: 注册到 Registry**

```python
# 在 core/publisher.py 底部
if HAS_INTERFACE:
    PublisherRegistry.register(GitLabPublisher)
```

---

## 附录: 技术栈

| 组件 | 版本 |
|------|------|
| Python | 3.8+ |
| PyQt5 | 5.15+ |
| requests | 2.25+ |
| PyInstaller | 5.0+ (构建) |

---

*文档更新日期: 2026-01-19*
