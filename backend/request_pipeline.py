"""Legacy module alias for application.request_pipeline."""
import sys
from application import request_pipeline as _implementation
sys.modules[__name__] = _implementation
