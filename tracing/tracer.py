#!/usr/bin/env python3
"""
Tracing System for Debugging Multi-Agent Systems
Integrates with LangSmith and Phoenix for visualization.
"""

import os
import json
import time
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

from orchestrator.models import TraceEvent


class TraceLevel(str, Enum):
    """Tracing verbosity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class Span:
    """Represents a trace span."""
    name: str
    agent_id: int
    start_time: float
    end_time: Optional[float] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[TraceEvent] = field(default_factory=list)
    parent_span_id: Optional[str] = None
    span_id: str = ""
    
    def __post_init__(self):
        import uuid
        self.span_id = str(uuid.uuid4())[:8]


class Tracer:
    """
    Tracing system for debugging multi-agent executions.
    Supports LangSmith and Phoenix integration.
    """
    
    def __init__(self, service_name: str = "agents-in-cahoots"):
        self.service_name = service_name
        self.spans: list[Span] = []
        self.events: list[TraceEvent] = []
        self._lock = Lock()
        
        self.langsmith_api_key = os.environ.get("LANGSMITH_API_KEY")
        self.langsmith_project = os.environ.get("LANGSMITH_PROJECT", "agents-in-cahoots")
        self.phoenix_enabled = os.environ.get("PHOENIX_ENABLED", "false").lower() == "true"
        
    def start_span(self, name: str, agent_id: int, 
                   attributes: Optional[dict] = None,
                   parent_span_id: Optional[str] = None) -> Span:
        """Start a new trace span."""
        span = Span(
            name=name,
            agent_id=agent_id,
            start_time=time.time(),
            attributes=attributes or {},
            parent_span_id=parent_span_id
        )
        
        with self._lock:
            self.spans.append(span)
        
        return span
    
    def end_span(self, span: Span, attributes: Optional[dict] = None):
        """End a trace span."""
        span.end_time = time.time()
        if attributes:
            span.attributes.update(attributes)
        
        if self.langsmith_api_key:
            self._send_to_langsmith(span)
        
        if self.phoenix_enabled:
            self._send_to_phoenix(span)
    
    def record_event(self, agent_id: int, event_type: str, 
                    details: Optional[dict] = None, duration_ms: Optional[float] = None):
        """Record a trace event."""
        event = TraceEvent(
            timestamp=datetime.now().isoformat(),
            agent_id=agent_id,
            event_type=event_type,
            details=details or {},
            duration_ms=duration_ms
        )
        
        with self._lock:
            self.events.append(event)
    
    def _send_to_langsmith(self, span: Span):
        """Send trace data to LangSmith."""
        import urllib.request
        import urllib.error
        
        if not self.langsmith_api_key:
            return
        
        data = {
            "name": span.name,
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "trace_id": self.service_name,
            "start_time_ms": int(span.start_time * 1000),
            "end_time_ms": int(span.end_time * 1000) if span.end_time else None,
            "attributes": span.attributes,
        }
        
        try:
            request = urllib.request.Request(
                f"https://api.langsmith.com/v1/runs",
                data=json.dumps(data).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.langsmith_api_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(request, timeout=5):
                pass
        except Exception:
            pass
    
    def _send_to_phoenix(self, span: Span):
        """Send trace data to Phoenix."""
        pass
    
    def get_trace(self, agent_id: Optional[int] = None) -> list[dict]:
        """Get trace data for analysis."""
        with self._lock:
            result = []
            
            for span in self.spans:
                if agent_id and span.agent_id != agent_id:
                    continue
                    
                duration = (span.end_time - span.start_time) if span.end_time else None
                
                result.append({
                    "span_id": span.span_id,
                    "name": span.name,
                    "agent_id": span.agent_id,
                    "start_time": span.start_time,
                    "end_time": span.end_time,
                    "duration_ms": duration * 1000 if duration else None,
                    "attributes": span.attributes,
                    "events": [e.model_dump() for e in span.events],
                    "parent_span_id": span.parent_span_id
                })
            
            return result
    
    def get_agent_timeline(self, agent_id: int) -> list[dict]:
        """Get timeline of all spans for an agent."""
        spans = [s for s in self.spans if s.agent_id == agent_id]
        spans.sort(key=lambda x: x.start_time)
        
        return [{
            "name": s.name,
            "start": s.start_time,
            "end": s.end_time,
            "duration": (s.end_time - s.start_time) * 1000 if s.end_time else None,
            "attributes": s.attributes
        } for s in spans]
    
    def get_summary(self) -> dict:
        """Get summary of all traces."""
        with self._lock:
            total_spans = len(self.spans)
            completed_spans = len([s for s in self.spans if s.end_time])
            
            total_duration = sum(
                s.end_time - s.start_time 
                for s in self.spans 
                if s.end_time
            )
            
            return {
                "service_name": self.service_name,
                "total_spans": total_spans,
                "completed_spans": completed_spans,
                "total_events": len(self.events),
                "total_duration_ms": total_duration * 1000,
                "langsmith_enabled": bool(self.langsmith_api_key),
                "phoenix_enabled": self.phoenix_enabled
            }
    
    def clear(self):
        """Clear all trace data."""
        with self._lock:
            self.spans.clear()
            self.events.clear()


tracer = Tracer()


def trace_agent_action(agent_id: int, action_name: str):
    """Decorator for tracing agent actions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            span = tracer.start_span(action_name, agent_id, {
                "function": func.__name__,
                "args": str(args)[:100],
                "kwargs": str(kwargs)[:100]
            })
            try:
                result = func(*args, **kwargs)
                tracer.end_span(span, {"success": True, "result": str(result)[:100]})
                return result
            except Exception as e:
                tracer.end_span(span, {"success": False, "error": str(e)})
                raise
        return wrapper
    return decorator
