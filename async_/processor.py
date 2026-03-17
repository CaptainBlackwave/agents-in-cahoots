#!/usr/bin/env python3
"""
Async Processing for Multi-Agent Systems
Uses asyncio for concurrent agent execution.
"""

import asyncio
import os
import json
import time
from datetime import datetime
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from orchestrator.models import AgentState, AgentAction
from orchestrator.state_machine import Orchestrator


class ExecutionMode(str, Enum):
    """Agent execution modes."""
    SEQUENTIAL = "sequential"
    CONCURRENT = "concurrent"
    PARALLEL = "parallel"


@dataclass
class AgentTask:
    """Represents a task for an agent."""
    agent_id: int
    task_type: str
    input_data: dict
    priority: int = 0


class AsyncOrchestrator(Orchestrator):
    """
    Async-aware orchestrator for concurrent agent execution.
    """
    
    def __init__(self, max_concurrent: int = 5, execution_mode: ExecutionMode = ExecutionMode.CONCURRENT):
        super().__init__(max_concurrent)
        self.execution_mode = execution_mode
        self.task_queue: asyncio.PriorityQueue = None
        self._running = False
        
    async def initialize(self):
        """Initialize async components."""
        self.task_queue = asyncio.PriorityQueue()
        self._running = True
    
    async def execute_agent_async(self, agent_id: int, action: AgentAction) -> tuple[bool, str]:
        """Execute an action asynchronously."""
        loop = asyncio.get_event_loop()
        
        def run_in_executor():
            return self.execute_agent(agent_id, action)
        
        return await loop.run_in_executor(None, run_in_executor)
    
    async def execute_tick_async(self, agent_actions: dict[int, AgentAction]) -> dict[int, tuple[bool, str]]:
        """
        Execute multiple agent actions concurrently.
        Returns mapping of agent_id to (success, message).
        """
        if self.execution_mode == ExecutionMode.SEQUENTIAL:
            return await self._execute_sequential(agent_actions)
        elif self.execution_mode == ExecutionMode.CONCURRENT:
            return await self._execute_concurrent(agent_actions)
        elif self.execution_mode == ExecutionMode.PARALLEL:
            return await self._execute_parallel(agent_actions)
        
        return {}
    
    async def _execute_sequential(self, agent_actions: dict[int, AgentAction]) -> dict[int, tuple[bool, str]]:
        """Execute agents sequentially."""
        results = {}
        
        for agent_id, action in agent_actions.items():
            success, message = await self.execute_agent_async(agent_id, action)
            results[agent_id] = (success, message)
        
        return results
    
    async def _execute_concurrent(self, agent_actions: dict[int, AgentAction]) -> dict[int, tuple[bool, str]]:
        """Execute agents concurrently with semaphore limiting."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def limited_execute(agent_id: int, action: AgentAction):
            async with semaphore:
                return await self.execute_agent_async(agent_id, action)
        
        tasks = [
            limited_execute(agent_id, action) 
            for agent_id, action in agent_actions.items()
        ]
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = {}
        for i, agent_id in enumerate(agent_actions.keys()):
            if isinstance(results_list[i], Exception):
                results[agent_id] = (False, str(results_list[i]))
            else:
                results[agent_id] = results_list[i]
        
        return results
    
    async def _execute_parallel(self, agent_actions: dict[int, AgentAction]) -> dict[int, tuple[bool, str]]:
        """Execute agents in parallel without limits."""
        tasks = [
            self.execute_agent_async(agent_id, action) 
            for agent_id, action in agent_actions.items()
        ]
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = {}
        for i, agent_id in enumerate(agent_actions.keys()):
            if isinstance(results_list[i], Exception):
                results[agent_id] = (False, str(results_list[i]))
            else:
                results[agent_id] = results_list[i]
        
        return results
    
    async def run_simulation_async(self, num_ticks: int, 
                                  agent_generator: Callable[[int], dict[int, AgentAction]],
                                  tick_delay: float = 1.0) -> dict:
        """Run simulation asynchronously."""
        await self.initialize()
        
        results = {
            "ticks": num_ticks,
            "completed_ticks": 0,
            "agent_results": {},
            "errors": []
        }
        
        for tick in range(num_ticks):
            try:
                agent_actions = agent_generator(tick)
                
                tick_results = await self.execute_tick_async(agent_actions)
                
                results["agent_results"][tick] = tick_results
                results["completed_ticks"] += 1
                
                if tick < num_ticks - 1:
                    await asyncio.sleep(tick_delay)
                    
            except Exception as e:
                results["errors"].append({
                    "tick": tick,
                    "error": str(e)
                })
        
        self._running = False
        return results
    
    async def process_task_queue(self):
        """Process tasks from the queue."""
        while self._running:
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                agent_id = task.agent_id
                action = AgentAction(**task.input_data.get("action", {}))
                
                success, message = await self.execute_agent_async(agent_id, action)
                
                self.task_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing task: {e}")
    
    async def shutdown(self):
        """Shutdown the async orchestrator."""
        self._running = False
        if self.task_queue:
            await self.task_queue.join()


async def run_agent_task(orchestrator: AsyncOrchestrator, agent_id: int, action: AgentAction):
    """Helper to run a single agent task."""
    return await orchestrator.execute_agent_async(agent_id, action)


async def run_parallel_agents(orchestrator: AsyncOrchestrator, 
                             agent_actions: list[tuple[int, AgentAction]]) -> list[tuple[bool, str]]:
    """Run multiple agents in parallel."""
    tasks = [
        run_agent_task(orchestrator, agent_id, action)
        for agent_id, action in agent_actions
    ]
    
    return await asyncio.gather(*tasks, return_exceptions=True)
