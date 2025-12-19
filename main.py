"""
Git Version Manager - Entry Point
"""
import sys
import os

# Add the package to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import main

if __name__ == "__main__":
    main()
