from contextvars import ContextVar
from typing import Optional

# Context variable to hold the current flow_id during agent execution
current_flow_id_var: ContextVar[Optional[str]] = ContextVar("current_flow_id", default=None) 