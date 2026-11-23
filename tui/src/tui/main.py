"""Console entry for aiditor-tui."""

from __future__ import annotations


def main() -> None:
    """Start the AIditor Textual app."""
    from tui.app import AiditorApp

    AiditorApp().run()


if __name__ == "__main__":
    main()
