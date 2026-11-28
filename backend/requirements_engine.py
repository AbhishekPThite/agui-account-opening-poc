"""Legacy module alias for domain.requirements."""
import sys
from domain import requirements as _implementation
sys.modules[__name__] = _implementation
