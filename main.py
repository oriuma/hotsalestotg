"""Entry point — delegates everything to src/main.py"""
import sys
import os

# Ensure project root is on path so `src` package is importable
sys.path.insert(0, os.path.dirname(__file__))

from src.main import main

if __name__ == "__main__":
    main()
