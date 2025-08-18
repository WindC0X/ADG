"""
DAG execution scheduler for the node engine.

This module implements a lightweight directed acyclic graph (DAG) scheduler that
manages node dependencies and orchestrates workflow execution while maintaining
memory efficiency.
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from core.node_interfaces import (
    ProcessingNode, NodeInput, NodeOutput, NodeStatus, 
    WorkflowContext, ValidationResult, ValidationSeverity
)
from core.node_engine.task_queue import SqliteTaskQueue, Task, create_task_id


logger = logging.getLogger(__name__)


@dataclass
class NodeDefinition:
    """Definition of a node in the workflow DAG."""
    node_id: str
    node_class: type
    config: Dict[str, Any]
    dependencies: List[str]
    priority: int = 0


@dataclass
class WorkflowDefinition:
    """Complete definition of a workflow DAG."""
    workflow_id: str
    name: str
    description: str
    nodes: Dict[str, NodeDefinition]
    initial_data: Dict[str, Any]
    
    def validate_dag(self) -> List[ValidationResult]:
        """Validate that the workflow forms a valid DAG."""
        results = []
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            node_def = self.nodes.get(node_id)
            if not node_def:
                return False
                
            for dep in node_def.dependencies:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        # Check each component
        for node_id in self.nodes:
            if node_id not in visited:
                if has_cycle(node_id):
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Cycle detected involving node '{node_id}'",
                        field_name="dependencies",
                        error_code="CYCLE_DETECTED"
                    ))
                    break
        
        # Check for missing dependencies
        for node_id, node_def in self.nodes.items():
            for dep in node_def.dependencies:
                if dep not in self.nodes:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Node '{node_id}' depends on missing node '{dep}'",
                        field_name="dependencies",
                        error_code="MISSING_DEPENDENCY"
                    ))
        
        # If no errors found, the DAG is valid
        if not any(r.severity == ValidationSeverity.ERROR for r in results):
            results.append(ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Workflow DAG is valid"
            ))
        
        return results


class NodeExecutor:
    """Handles execution of individual nodes with memory monitoring."""
    
    def __init__(self, max_memory_mb: float = 40.0):
        """
        Initialize the node executor.
        
        Args:
            max_memory_mb: Maximum memory usage per node before warnings.
        """
        self.max_memory_mb = max_memory_mb
        
    def execute_node(self, node: ProcessingNode, input_data: NodeInput) -> NodeOutput:
        """
        Execute a single node with memory monitoring.
        
        Args:
            node: The node to execute.
            input_data: Input data for the node.
            
        Returns:
            The output from node execution.
        """
        start_time = time.perf_counter()
        
        try:
            # Validate input first
            validation_results = node.validate_input(input_data)
            error_results = [r for r in validation_results if r.severity == ValidationSeverity.ERROR]
            
            if error_results:
                error_messages = [r.message for r in error_results]
                output = NodeOutput(
                    data={},
                    node_id=node.node_id,
                    status=NodeStatus.FAILED,
                    errors=error_messages
                )
                return output
            
            # Add warnings to metadata
            warning_results = [r for r in validation_results if r.severity == ValidationSeverity.WARNING]
            if warning_results:
                input_data.metadata["validation_warnings"] = [r.message for r in warning_results]
            
            # Execute the node
            logger.info(f"Starting execution of node {node.node_id}")
            output = node.process(input_data)
            
            # Calculate processing time
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            output.processing_time_ms = processing_time_ms
            
            # Monitor memory usage
            memory_usage = node.get_memory_usage()
            if memory_usage > self.max_memory_mb:
                logger.warning(f"Node {node.node_id} exceeded memory budget: {memory_usage:.1f}MB")
                output.add_warning(f"Memory usage exceeded budget: {memory_usage:.1f}MB")
            
            logger.info(f"Node {node.node_id} completed in {processing_time_ms:.1f}ms")
            return output
            
        except Exception as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Node {node.node_id} failed: {e}", exc_info=True)
            
            return NodeOutput(
                data={},
                node_id=node.node_id,
                status=NodeStatus.FAILED,
                processing_time_ms=processing_time_ms,
                errors=[str(e)]
            )


class DAGScheduler:
    """
    DAG execution scheduler with dependency resolution.
    
    Manages workflow execution by scheduling nodes based on their dependencies
    and maintaining execution state through the task queue.
    """
    
    def __init__(self, task_queue: SqliteTaskQueue, max_workers: int = 4):
        """
        Initialize the DAG scheduler.
        
        Args:
            task_queue: Task queue for managing node execution.
            max_workers: Maximum number of concurrent node executions.
        """
        self.task_queue = task_queue
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.node_executor = NodeExecutor()
        self.active_workflows: Dict[str, WorkflowContext] = {}
        self.node_registry: Dict[str, type] = {}
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        
    def register_node_type(self, node_type: type, type_name: str) -> None:
        """Register a node type for dynamic instantiation."""
        self.node_registry[type_name] = node_type
        logger.info(f"Registered node type: {type_name}")
    
    def start(self) -> None:
        """Start the scheduler worker thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            logger.warning("Scheduler is already running")
            return
        
        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("DAG scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler worker thread."""
        self._shutdown_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        self.executor.shutdown(wait=True)
        logger.info("DAG scheduler stopped")
    
    def submit_workflow(self, workflow_def: WorkflowDefinition) -> str:
        """
        Submit a workflow for execution.
        
        Args:
            workflow_def: The workflow definition to execute.
            
        Returns:
            The workflow execution ID.
        """
        # Validate the workflow DAG
        validation_results = workflow_def.validate_dag()
        error_results = [r for r in validation_results if r.severity == ValidationSeverity.ERROR]
        
        if error_results:
            error_msg = "; ".join(r.message for r in error_results)
            raise ValueError(f"Invalid workflow DAG: {error_msg}")
        
        # Create workflow context
        context = WorkflowContext(
            workflow_id=workflow_def.workflow_id,
            status=NodeStatus.PENDING
        )
        context.set_shared_data("initial_data", workflow_def.initial_data)
        context.set_shared_data("workflow_name", workflow_def.name)
        
        # Save workflow context
        self.task_queue.save_workflow_context(context)
        self.active_workflows[workflow_def.workflow_id] = context
        
        # Create tasks for all nodes
        for node_id, node_def in workflow_def.nodes.items():
            task_id = create_task_id()
            
            # Create input data with workflow context
            input_data = NodeInput(
                data=workflow_def.initial_data.copy(),
                metadata={
                    "workflow_id": workflow_def.workflow_id,
                    "node_config": node_def.config,
                    "node_class": node_def.node_class.__name__
                },
                node_id=node_id
            )
            
            task = Task(
                task_id=task_id,
                node_id=node_id,
                workflow_id=workflow_def.workflow_id,
                input_data=input_data,
                dependencies=[f"{workflow_def.workflow_id}:{dep}" for dep in node_def.dependencies],
                priority=node_def.priority
            )
            
            self.task_queue.add_task(task)
        
        logger.info(f"Submitted workflow {workflow_def.workflow_id} with {len(workflow_def.nodes)} nodes")
        return workflow_def.workflow_id
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a workflow."""
        context = self.task_queue.get_workflow_context(workflow_id)
        if not context:
            return None
        
        tasks = self.task_queue.get_workflow_tasks(workflow_id)
        task_statuses = {}
        
        for task in tasks:
            task_statuses[task.node_id] = {
                "status": task.status.name,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "retry_count": task.retry_count,
                "error_message": task.error_message
            }
        
        return {
            "workflow_id": workflow_id,
            "status": context.status.name,
            "started_at": context.started_at.isoformat(),
            "completed_at": context.completed_at.isoformat() if context.completed_at else None,
            "current_node": context.current_node_id,
            "tasks": task_statuses
        }
    
    def _worker_loop(self) -> None:
        """Main worker loop for processing tasks."""
        logger.info("Scheduler worker loop started")
        
        while not self._shutdown_event.is_set():
            try:
                # Get next ready task
                task = self.task_queue.get_next_ready_task()
                
                if task is None:
                    # No tasks ready, wait a bit
                    time.sleep(0.1)
                    continue
                
                # Submit task for execution
                future = self.executor.submit(self._execute_task, task)
                
                # Don't wait for completion here - let it run concurrently
                # The task completion will be handled in _execute_task
                
            except Exception as e:
                logger.error(f"Error in scheduler worker loop: {e}", exc_info=True)
                time.sleep(1.0)  # Back off on errors
        
        logger.info("Scheduler worker loop stopped")
    
    def _execute_task(self, task: Task) -> None:
        """Execute a single task."""
        try:
            # Get node class from metadata
            node_class_name = task.input_data.metadata.get("node_class")
            if not node_class_name or node_class_name not in self.node_registry:
                raise ValueError(f"Unknown node class: {node_class_name}")
            
            # Create node instance
            node_class = self.node_registry[node_class_name]
            node_config = task.input_data.metadata.get("node_config", {})
            node = node_class(task.node_id, node_config)
            
            # Update workflow context
            workflow_id = task.workflow_id
            if workflow_id in self.active_workflows:
                context = self.active_workflows[workflow_id]
                context.current_node_id = task.node_id
                context.status = NodeStatus.RUNNING
                self.task_queue.save_workflow_context(context)
            
            # Execute the node
            output = self.node_executor.execute_node(node, task.input_data)
            
            if output.status == NodeStatus.COMPLETED:
                # Task completed successfully
                self.task_queue.complete_task(task.task_id, output)
                logger.info(f"Task {task.task_id} completed successfully")
                
                # Check if workflow is complete
                self._check_workflow_completion(workflow_id)
                
            else:
                # Task failed
                error_msg = "; ".join(output.errors) if output.errors else "Unknown error"
                retry_attempted = self.task_queue.fail_task(task.task_id, error_msg, retry=True)
                
                if retry_attempted:
                    logger.warning(f"Task {task.task_id} failed, will retry: {error_msg}")
                else:
                    logger.error(f"Task {task.task_id} permanently failed: {error_msg}")
                    self._handle_workflow_failure(workflow_id, task.node_id, error_msg)
        
        except Exception as e:
            logger.error(f"Exception executing task {task.task_id}: {e}", exc_info=True)
            self.task_queue.fail_task(task.task_id, str(e), retry=True)
    
    def _check_workflow_completion(self, workflow_id: str) -> None:
        """Check if a workflow has completed and update its status."""
        tasks = self.task_queue.get_workflow_tasks(workflow_id)
        
        all_completed = all(task.status in [NodeStatus.COMPLETED, NodeStatus.FAILED] for task in tasks)
        any_failed = any(task.status == NodeStatus.FAILED for task in tasks)
        
        if all_completed:
            context = self.active_workflows.get(workflow_id)
            if context:
                context.completed_at = datetime.utcnow()
                context.status = NodeStatus.FAILED if any_failed else NodeStatus.COMPLETED
                context.current_node_id = None
                
                self.task_queue.save_workflow_context(context)
                
                if workflow_id in self.active_workflows:
                    del self.active_workflows[workflow_id]
                
                status_msg = "failed" if any_failed else "completed"
                logger.info(f"Workflow {workflow_id} {status_msg}")
    
    def _handle_workflow_failure(self, workflow_id: str, failed_node_id: str, error_msg: str) -> None:
        """Handle a workflow failure due to a node failure."""
        context = self.active_workflows.get(workflow_id)
        if context:
            context.completed_at = datetime.utcnow()
            context.status = NodeStatus.FAILED
            context.current_node_id = failed_node_id
            
            # Add failure information to execution state
            context.update_execution_state(failed_node_id, {
                "status": "failed",
                "error": error_msg,
                "failed_at": datetime.utcnow().isoformat()
            })
            
            self.task_queue.save_workflow_context(context)
            
            if workflow_id in self.active_workflows:
                del self.active_workflows[workflow_id]
            
            logger.error(f"Workflow {workflow_id} failed due to node {failed_node_id}: {error_msg}")


def create_workflow_id() -> str:
    """Generate a unique workflow ID."""
    return f"workflow_{str(uuid4())[:8]}"