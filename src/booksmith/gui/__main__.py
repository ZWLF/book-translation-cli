try:
    # Normal package execution: `python -m booksmith.gui`
    from .app import main
except ImportError:
    # Frozen/packaged execution path where relative imports may lose package context.
    from booksmith.gui.app import main

if __name__ == "__main__":
    main()
