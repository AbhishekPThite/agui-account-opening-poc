"""Legacy module alias for application.request_extraction."""
import sys
from application import request_extraction as _implementation
sys.modules[__name__] = _implementation
