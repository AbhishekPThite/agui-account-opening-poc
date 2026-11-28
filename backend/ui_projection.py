"""Legacy module alias for presentation.ui_projection."""
import sys
from presentation import ui_projection as _implementation
sys.modules[__name__] = _implementation
