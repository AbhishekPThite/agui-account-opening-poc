"""Legacy module alias for integrations.llm.model_client."""
import sys
from integrations.llm import model_client as _implementation
sys.modules[__name__] = _implementation
