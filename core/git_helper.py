"""
Git Helper - Core git operations
"""
import subprocess
import os
from typing import Optional, Tuple, List


class GitHelper:
    """Helper class for git operations."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        
    def _run_git(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command."""
        cmd = ["git"] + args
        try:
            return subprocess.run(
                cmd, 
                cwd=self.repo_path, 
                capture_output=True, 
                encoding='utf-8', 
                errors='ignore',
                check=check,
                timeout=10  # 防止网络慢时卡死
            )
        except subprocess.TimeoutExpired as e:
            print(f"Git command timed out: {cmd}")
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=f"Command timed out after 10s: {str(e)}"
            )
    
    def is_git_repo(self) -> bool:
        """Check if the path is a git repository."""
        return os.path.exists(os.path.join(self.repo_path, ".git"))
    
    def has_remote(self, remote_name: str = "origin") -> bool:
        """Check if a remote exists."""
        result = self._run_git(["remote"], check=False)
        return remote_name in result.stdout.split()
    
    def get_remotes(self) -> List[dict]:
        """Get list of remotes with their URLs."""
        result = self._run_git(["remote", "-v"], check=False)
        remotes = {}
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    name, url = parts[0], parts[1]
                    if name not in remotes:
                        remotes[name] = url
        return [{"name": k, "url": v} for k, v in remotes.items()]
    
    def fetch(self, remote: str = "origin") -> bool:
        """Fetch from remote."""
        try:
            self._run_git(["fetch", remote])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def has_local_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        result = self._run_git(["status", "--porcelain"], check=False)
        return bool(result.stdout.strip())
    
    def get_changed_files(self) -> List[str]:
        """Get list of changed files."""
        result = self._run_git(["status", "--porcelain"], check=False)
        files = []
        for line in result.stdout.strip().split('\n'):
            if line:
                files.append(line[3:])  # Skip status prefix
        return files
    
    def get_local_head(self) -> Optional[str]:
        """Get local HEAD commit hash."""
        result = self._run_git(["rev-parse", "HEAD"], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    
    def get_remote_head(self, remote: str = "origin", branch: str = "HEAD") -> Optional[str]:
        """Get remote HEAD commit hash."""
        result = self._run_git(["rev-parse", f"{remote}/{branch}"], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    
    def is_ahead_of_remote(self, remote: str = "origin") -> Tuple[int, int]:
        """
        Check if local is ahead/behind remote.
        Returns (ahead_count, behind_count).
        """
        result = self._run_git(
            ["rev-list", "--left-right", "--count", f"HEAD...{remote}/HEAD"],
            check=False
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split()
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        return 0, 0
    
    def get_current_branch(self) -> Optional[str]:
        """Get current branch name."""
        result = self._run_git(["branch", "--show-current"], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    
    def commit(self, message: str, add_all: bool = True) -> bool:
        """Commit changes."""
        try:
            if add_all:
                self._run_git(["add", "-A"])
            self._run_git(["commit", "-m", message])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def push(self, remote: str = "origin", branch: Optional[str] = None) -> bool:
        """Push to remote."""
        try:
            args = ["push", remote]
            if branch:
                args.append(branch)
            self._run_git(args)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def pull(self, remote: str = "origin") -> bool:
        """Pull from remote."""
        try:
            self._run_git(["pull", remote])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_remote_file_content(self, filepath: str, remote: str = "origin", ref: str = None) -> Optional[str]:
        """Get content of a file from remote."""
        # Use current branch if ref not specified
        if ref is None:
            ref = self.get_current_branch() or "main"
        result = self._run_git(["show", f"{remote}/{ref}:{filepath}"], check=False)
        if result.returncode == 0:
            return result.stdout
        return None
    
    def create_tag(self, tag_name: str, message: str = "") -> bool:
        """Create a git tag."""
        try:
            if message:
                self._run_git(["tag", "-a", tag_name, "-m", message])
            else:
                self._run_git(["tag", tag_name])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def push_tags(self, remote: str = "origin") -> bool:
        """Push tags to remote."""
        try:
            self._run_git(["push", remote, "--tags"])
            return True
        except subprocess.CalledProcessError:
            return False
    
    # Remote management methods
    def add_remote(self, name: str, url: str) -> bool:
        """Add a new remote."""
        try:
            self._run_git(["remote", "add", name, url])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def set_remote_url(self, name: str, url: str) -> bool:
        """Set URL for an existing remote."""
        try:
            self._run_git(["remote", "set-url", name, url])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def remove_remote(self, name: str) -> bool:
        """Remove a remote."""
        try:
            self._run_git(["remote", "remove", name])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def rename_remote(self, old_name: str, new_name: str) -> bool:
        """Rename a remote."""
        try:
            self._run_git(["remote", "rename", old_name, new_name])
            return True
        except subprocess.CalledProcessError:
            return False
    
    @staticmethod
    def parse_repo_from_url(url: str) -> Optional[str]:
        """
        Extract username/repo from a git URL.
        Supports: https://github.com/user/repo.git, git@github.com:user/repo.git
        """
        import re
        # HTTPS format
        https_match = re.search(r'https?://[^/]+/([^/]+/[^/]+?)(?:\.git)?$', url)
        if https_match:
            return https_match.group(1)
        
        # SSH format
        ssh_match = re.search(r'git@[^:]+:([^/]+/[^/]+?)(?:\.git)?$', url)
        if ssh_match:
            return ssh_match.group(1)
        
        return None
    
    @staticmethod
    def detect_platform_from_url(url: str) -> Optional[str]:
        """Detect git platform from URL."""
        url_lower = url.lower()
        if 'github.com' in url_lower:
            return 'github'
        elif 'gitee.com' in url_lower:
            return 'gitee'
        elif 'gitea' in url_lower or 'git.' in url_lower:
            # Generic gitea detection (may need custom URL)
            return 'gitea'
        return None
    
    def get_remotes_with_details(self) -> List[dict]:
        """
        Get remotes with platform and repo details.
        Returns list of dicts with: name, url, platform, repo
        """
        remotes = self.get_remotes()
        for remote in remotes:
            url = remote.get('url', '')
            remote['platform'] = self.detect_platform_from_url(url)
            remote['repo'] = self.parse_repo_from_url(url)
        return remotes
    
    # Sync and conflict handling methods
    def pull_rebase(self, remote: str = "origin", branch: Optional[str] = None) -> Tuple[bool, str]:
        """
        Pull with rebase from remote.
        Returns (success, message).
        """
        branch = branch or self.get_current_branch() or "main"
        result = self._run_git(["pull", "--rebase", remote, branch], check=False)
        
        if result.returncode == 0:
            return True, "Pull rebase successful"
        
        # Check for conflicts
        if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
            return False, "Merge conflicts detected"
        
        return False, result.stderr.strip() or result.stdout.strip() or "Pull failed"
    
    def force_push(self, remote: str = "origin", branch: Optional[str] = None) -> Tuple[bool, str]:
        """
        Force push to remote.
        Returns (success, message).
        """
        branch = branch or self.get_current_branch() or "main"
        result = self._run_git(["push", "--force", remote, branch], check=False)
        
        if result.returncode == 0:
            return True, "Force push successful"
        
        return False, result.stderr.strip() or result.stdout.strip() or "Push failed"
    
    def get_remote_status(self, remote: str = "origin") -> dict:
        """
        Get detailed status for a specific remote.
        Returns dict with: ahead, behind, can_push, can_pull, error
        """
        branch = self.get_current_branch() or "main"
        
        # Fetch first
        self.fetch(remote)
        
        # Get ahead/behind counts
        result = self._run_git(
            ["rev-list", "--left-right", "--count", f"HEAD...{remote}/{branch}"],
            check=False
        )
        
        status = {
            "remote": remote,
            "branch": branch,
            "ahead": 0,
            "behind": 0,
            "can_push": True,
            "can_pull": True,
            "error": None
        }
        
        if result.returncode == 0:
            parts = result.stdout.strip().split()
            if len(parts) == 2:
                status["ahead"] = int(parts[0])
                status["behind"] = int(parts[1])
                
                # Can't fast-forward push if behind
                if status["behind"] > 0:
                    status["can_push"] = False
        else:
            status["error"] = result.stderr.strip() or "Unknown error"
        
        return status
    
    def has_merge_conflicts(self) -> bool:
        """Check if there are merge conflicts."""
        result = self._run_git(["diff", "--name-only", "--diff-filter=U"], check=False)
        return bool(result.stdout.strip())
    
    def get_conflict_files(self) -> List[str]:
        """Get list of files with merge conflicts."""
        result = self._run_git(["diff", "--name-only", "--diff-filter=U"], check=False)
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split('\n') if f]
        return []
    
    def abort_rebase(self) -> bool:
        """Abort an ongoing rebase."""
        try:
            self._run_git(["rebase", "--abort"])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def abort_merge(self) -> bool:
        """Abort an ongoing merge."""
        try:
            self._run_git(["merge", "--abort"])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def open_in_vscode(self) -> bool:
        """Open the repository in VS Code."""
        try:
            import subprocess
            subprocess.Popen(["code", self.repo_path], shell=True)
            return True
        except Exception:
            return False

