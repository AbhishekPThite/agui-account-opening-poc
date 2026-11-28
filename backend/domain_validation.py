"""Legacy module alias for domain.validation."""
import sys
from domain import validation as _implementation
sys.modules[__name__] = _implementation
