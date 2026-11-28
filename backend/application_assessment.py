"""Legacy module alias for domain.assessment."""
import sys
from domain import assessment as _implementation
sys.modules[__name__] = _implementation
