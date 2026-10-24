"""
Desktop tool adapter package.
"""

from app.tools.desktop.adapter import DesktopToolAdapter
from app.tools.desktop.driver import DesktopDriver, MockDesktopDriver

__all__ = ["DesktopToolAdapter", "DesktopDriver", "MockDesktopDriver"]
