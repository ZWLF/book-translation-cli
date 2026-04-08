import os

# Skip pydantic plugin discovery during GUI startup to reduce cold-start overhead.
os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")

try:
    # Normal package execution: `python -m booksmith.gui`
    from .app import main
except ImportError:
    # Frozen/packaged execution path where relative imports may lose package context.
    from booksmith.gui.app import main

if __name__ == "__main__":
    main()
