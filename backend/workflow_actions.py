"""Legacy module alias for application.workflow_actions."""
import sys
from application import workflow_actions as _implementation
sys.modules[__name__] = _implementation
