"""
Entry point for running BOUT as a module.

Usage: python -m bout [command] [options]
"""
from .cli import main

if __name__ == "__main__":
    main()
