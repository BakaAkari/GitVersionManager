"""
Packager - Create clean ZIP packages
"""
import os
import zipfile
import shutil
from typing import List, Optional
from datetime import datetime


class Packager:
    """Create clean ZIP packages of projects."""
    
    DEFAULT_IGNORE = [
        '.git', '.idea', '.vscode', '__pycache__', 
        '.gitignore', '.gitattributes', '.DS_Store',
        '*.pyc', '*.pyo', '.env', '.venv', 'venv',
        'node_modules', '*.log', '.pytest_cache'
    ]
    
    def __init__(self, project_path: str, project_name: str, archive_path: Optional[str] = None):
        self.project_path = project_path
        self.project_name = project_name
        self.archive_path = archive_path or os.path.dirname(project_path)
        self.ignore_patterns = self.DEFAULT_IGNORE.copy()
    
    def add_ignore_pattern(self, pattern: str):
        """Add a pattern to ignore list."""
        if pattern not in self.ignore_patterns:
            self.ignore_patterns.append(pattern)
    
    def set_ignore_patterns(self, patterns: List[str]):
        """Set the ignore patterns."""
        self.ignore_patterns = patterns
    
    def _should_ignore(self, name: str) -> bool:
        """Check if a file/directory should be ignored."""
        for pattern in self.ignore_patterns:
            if pattern.startswith('*'):
                # Extension pattern
                ext = pattern[1:]
                if name.endswith(ext):
                    return True
            elif name == pattern:
                return True
        return False
    
    def create_zip(self, version: str, include_version_in_name: bool = True) -> str:
        """
        Create a ZIP file of the project.
        Returns the path to the created ZIP file.
        """
        if include_version_in_name:
            zip_filename = f"{self.project_name}_v{version}.zip"
        else:
            zip_filename = f"{self.project_name}.zip"
        
        # Ensure archive directory exists
        os.makedirs(self.archive_path, exist_ok=True)
        
        output_path = os.path.join(self.archive_path, zip_filename)
        
        # Remove existing file if present
        if os.path.exists(output_path):
            os.remove(output_path)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.project_path):
                # Filter directories in place
                dirs[:] = [d for d in dirs if not self._should_ignore(d)]
                
                for file in files:
                    if self._should_ignore(file):
                        continue
                    
                    file_path = os.path.join(root, file)
                    # Create archive path with project name as root
                    rel_path = os.path.relpath(file_path, self.project_path)
                    arcname = os.path.join(self.project_name, rel_path)
                    
                    zipf.write(file_path, arcname)
        
        return output_path
    
    def create_dist_zip(self, version: str, include_version_in_name: bool = True) -> str:
        """
        Create a ZIP file of the dist/ folder only (for compiled executables).
        Returns the path to the created ZIP file.
        """
        dist_path = os.path.join(self.project_path, "dist")
        
        # Check if dist folder exists
        if not os.path.exists(dist_path):
            raise FileNotFoundError(f"dist/ folder not found in {self.project_path}")
        
        # Find the main folder inside dist (e.g., dist/GitVersionManager/)
        dist_contents = os.listdir(dist_path)
        main_folder = None
        for item in dist_contents:
            item_path = os.path.join(dist_path, item)
            if os.path.isdir(item_path):
                main_folder = item_path
                break
        
        # If no subfolder, use dist itself
        source_path = main_folder if main_folder else dist_path
        
        if include_version_in_name:
            zip_filename = f"{self.project_name}_v{version}.zip"
        else:
            zip_filename = f"{self.project_name}.zip"
        
        # Ensure archive directory exists
        os.makedirs(self.archive_path, exist_ok=True)
        
        output_path = os.path.join(self.archive_path, zip_filename)
        
        # Remove existing file if present
        if os.path.exists(output_path):
            os.remove(output_path)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Create archive path with project name as root
                    rel_path = os.path.relpath(file_path, source_path)
                    arcname = os.path.join(self.project_name, rel_path)
                    zipf.write(file_path, arcname)
        
        return output_path
    
    def get_archive_history(self) -> List[dict]:
        """Get list of archived versions."""
        history = []
        if not os.path.exists(self.archive_path):
            return history
        
        prefix = f"{self.project_name}_v"
        for filename in os.listdir(self.archive_path):
            if filename.startswith(prefix) and filename.endswith('.zip'):
                filepath = os.path.join(self.archive_path, filename)
                stat = os.stat(filepath)
                # Extract version from filename
                version = filename[len(prefix):-4]  # Remove prefix and .zip
                history.append({
                    "filename": filename,
                    "version": version,
                    "path": filepath,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime)
                })
        
        # Sort by version (newest first)
        history.sort(key=lambda x: x["version"], reverse=True)
        return history
