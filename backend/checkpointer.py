"""Legacy module alias for infrastructure.checkpointer."""
import sys
from infrastructure import checkpointer as _implementation
sys.modules[__name__] = _implementation
