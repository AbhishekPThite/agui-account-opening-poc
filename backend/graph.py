"""Compatibility entry point preserving legacy monkeypatch behavior.

The original graph module exposed both node functions and graph topology from one
module. Alias this module to the node implementation so tests and local callers
that patch graph.model or extraction functions still patch the globals used by
the node functions.
"""
import sys

from workflow import nodes as _nodes
from workflow import graph as _topology

_nodes.route_after_request = _topology.route_after_request
_nodes.route_after_status = _topology.route_after_status
_nodes.route_after_approval = _topology.route_after_approval
_nodes.build_graph = _topology.build_graph

sys.modules[__name__] = _nodes
