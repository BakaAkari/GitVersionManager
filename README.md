# Git Version Manager

A PyQt5-based GUI tool for managing and publishing releases to GitHub, Gitee, and Gitea platforms.

## Features

- 🔄 **Multi-project management** - Manage multiple Git projects
- 📊 **Per-platform version display** - Show version status for each remote
- ⬆️ **Auto version bump** - Increment patch version with one click
- 📦 **Clean packaging** - Create ZIP archives excluding dev files
- 🚀 **Multi-platform release** - Publish to GitHub, Gitee, Gitea simultaneously
- 🔄 **Sync management** - Pull, push, force push with conflict detection
- 📝 **VS Code integration** - Resolve conflicts in VS Code

## Installation

```bash
pip install -r requirements.txt
python main.py
```

## Requirements

- Python 3.8+
- PyQt5
- requests
- Git

## Usage

1. Click **+ 添加** to add a project
2. Configure remotes in project settings
3. Use **🔄 刷新** to check status
4. Use **📦 打包** to create ZIP
5. Use **🚀 发布** to publish releases to all platforms

## Configuration

API tokens are stored in `~/.git_version_manager/config.json`

## License

MIT
