"""Legacy module alias for application.state_updates."""
import sys
from application import state_updates as _implementation
sys.modules[__name__] = _implementation
