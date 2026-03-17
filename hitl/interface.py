#!/usr/bin/env python3
"""
Human-in-the-Loop (HITL) Interface
Allows humans to intervene, approve plans, or provide feedback.
"""

import asyncio
import threading
from datetime import datetime
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty

from orchestrator.models import HumanFeedback, AgentAction


class HITLMode(str, Enum):
    """HITL operation modes."""
    DISABLED = "disabled"
    APPROVAL = "approval"
    FEEDBACK = "feedback"
    FULL = "full"


@dataclass
class ApprovalRequest:
    """Request for human approval."""
    request_id: str
    agent_id: int
    action: AgentAction
    context: dict
    timestamp: str
    status: str = "pending"
    

class HumanInTheLoop:
    """
    Human-in-the-Loop interface for agent oversight.
    Allows humans to approve, reject, or modify agent actions.
    """
    
    def __init__(self, mode: HITLMode = HITLMode.APPROVAL):
        self.mode = mode
        self.approval_queue: Queue = Queue()
        self.feedback_history: list[HumanFeedback] = []
        self.callbacks: dict[str, Callable] = {}
        self.pending_requests: dict[str, ApprovalRequest] = {}
        self._lock = threading.Lock()
        
    def set_mode(self, mode: HITLMode):
        """Change the HITL mode."""
        self.mode = mode
    
    def request_approval(self, agent_id: int, action: AgentAction, 
                        context: Optional[dict] = None) -> str:
        """
        Request human approval for an action.
        Returns request_id for tracking.
        """
        if self.mode == HITLMode.DISABLED:
            return ""
        
        import uuid
        request_id = str(uuid.uuid4())[:8]
        
        request = ApprovalRequest(
            request_id=request_id,
            agent_id=agent_id,
            action=action,
            context=context or {},
            timestamp=datetime.now().isoformat()
        )
        
        with self._lock:
            self.pending_requests[request_id] = request
        
        self.approval_queue.put(request)
        
        if self._on_approval_request:
            self._on_approval_request(request)
        
        return request_id
    
    def approve(self, request_id: str, modified_action: Optional[AgentAction] = None) -> bool:
        """
        Approve a pending request.
        Optionally provide a modified action.
        """
        with self._lock:
            if request_id not in self.pending_requests:
                return False
            
            request = self.pending_requests[request_id]
            request.status = "approved"
            
            feedback = HumanFeedback(
                agent_id=request.agent_id,
                approved=True,
                modified_action=modified_action,
                timestamp=datetime.now().isoformat()
            )
            
            self.feedback_history.append(feedback)
            del self.pending_requests[request_id]
            
            return True
    
    def reject(self, request_id: str, reason: str) -> bool:
        """Reject a pending request."""
        with self._lock:
            if request_id not in self.pending_requests:
                return False
            
            request = self.pending_requests[request_id]
            request.status = "rejected"
            
            feedback = HumanFeedback(
                agent_id=request.agent_id,
                approved=False,
                feedback=reason,
                timestamp=datetime.now().isoformat()
            )
            
            self.feedback_history.append(feedback)
            del self.pending_requests[request_id]
            
            return True
    
    def provide_feedback(self, agent_id: int, feedback: str):
        """Provide general feedback to an agent."""
        human_feedback = HumanFeedback(
            agent_id=agent_id,
            approved=True,
            feedback=feedback,
            timestamp=datetime.now().isoformat()
        )
        
        with self._lock:
            self.feedback_history.append(human_feedback)
        
        if self._on_feedback:
            self._on_feedback(human_feedback)
    
    def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        with self._lock:
            return list(self.pending_requests.values())
    
    def get_feedback_for_agent(self, agent_id: int) -> list[HumanFeedback]:
        """Get all feedback for a specific agent."""
        with self._lock:
            return [f for f in self.feedback_history if f.agent_id == agent_id]
    
    def wait_for_approval(self, request_id: str, timeout: float = 60.0) -> tuple[bool, Optional[AgentAction]]:
        """
        Wait for approval with timeout.
        Returns (approved, modified_action).
        """
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            with self._lock:
                if request_id not in self.pending_requests:
                    request = [r for r in self.feedback_history 
                              if r.agent_id == self.pending_requests.get(request_id, ApprovalRequest("", 0, AgentAction(action="wait"), {}, "")).agent_id]
                    if request:
                        return request[-1].approved, request[-1].modified_action
            
            import time
            time.sleep(0.1)
        
        return False, None
    
    def register_callback(self, event: str, callback: Callable):
        """Register a callback for HITL events."""
        self.callbacks[event] = callback
    
    def _handle_approval_request(self, request: ApprovalRequest):
        """Handle approval request via callback."""
        if "approval_request" in self.callbacks:
            self.callbacks["approval_request"](request)
    
    def _handle_feedback(self, feedback: HumanFeedback):
        """Handle feedback via callback."""
        if "feedback" in self.callbacks:
            self.callbacks["feedback"](feedback)
    
    @property
    def _on_approval_request(self):
        return self.callbacks.get("approval_request")
    
    @property
    def _on_feedback(self):
        return self.callbacks.get("feedback")
    
    def get_status(self) -> dict:
        """Get HITL status."""
        return {
            "mode": self.mode.value,
            "pending_requests": len(self.pending_requests),
            "total_feedback": len(self.feedback_history)
        }


class CLIHITL(HumanInTheLoop):
    """CLI-based implementation of HITL."""
    
    def __init__(self):
        super().__init__(HITLMode.APPROVAL)
        self._running = False
    
    def start(self):
        """Start the CLI interface."""
        self._running = True
        threading.Thread(target=self._cli_loop, daemon=True).start()
    
    def _cli_loop(self):
        """CLI input loop."""
        while self._running:
            try:
                requests = self.get_pending_requests()
                if requests:
                    print(f"\n=== Approval Request ===")
                    for req in requests:
                        print(f"Agent {req.agent_id}: {req.action.action}")
                        if req.action.dialogue:
                            print(f"  Dialogue: {req.action.dialogue}")
                        
                        response = input("Approve (a), Reject (r), Modify (m)? ").strip().lower()
                        
                        if response == 'a':
                            self.approve(req.request_id)
                        elif response == 'r':
                            reason = input("Reason: ").strip()
                            self.reject(req.request_id, reason)
                        elif response == 'm':
                            new_dialogue = input("New dialogue: ").strip()
                            req.action.dialogue = new_dialogue
                            self.approve(req.request_id, req.action)
                
                import time
                time.sleep(1)
                
            except KeyboardInterrupt:
                self._running = False
                break
    
    def stop(self):
        """Stop the CLI interface."""
        self._running = False
