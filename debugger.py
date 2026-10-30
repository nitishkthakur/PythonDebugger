#!/usr/bin/env python3
"""Compatibility launcher; implementation lives in app/."""
import sys
import os

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.debugger import main

if __name__ == "__main__":
    main(sys.argv)
