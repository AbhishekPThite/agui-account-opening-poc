"""Legacy module alias for integrations.java.enterprise_api."""
import sys
from integrations.java import enterprise_api as _implementation
sys.modules[__name__] = _implementation
