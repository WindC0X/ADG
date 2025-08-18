"""
SQLite-based task queue for the node execution engine.

This module implements a lightweight, WAL-mode SQLite task queue designed to stay
within the 50MB memory budget while providing reliable task persistence and execution tracking.
"""

import sqlite3
import json
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator
from uuid import uuid4

from core.node_interfaces import NodeStatus, WorkflowContext, NodeInput, NodeOutput


class TaskQueueError(Exception):
    """Base exception for task queue operations."""
    pass


class TaskNotFoundError(TaskQueueError):
    """Raised when a task is not found in the queue."""
    pass


class Task:
    """Represents a task in the execution queue."""
    
    def __init__(self, task_id: str, node_id: str, workflow_id: str, 
                 input_data: NodeInput, dependencies: Optional[List[str]] = None,
                 priority: int = 0, max_retries: int = 3):
        self.task_id = task_id
        self.node_id = node_id
        self.workflow_id = workflow_id
        self.input_data = input_data
        self.dependencies = dependencies or []
        self.priority = priority
        self.max_retries = max_retries
        self.retry_count = 0
        self.status = NodeStatus.PENDING
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.output_data: Optional[NodeOutput] = None
        self.error_message: Optional[str] = None


class SqliteTaskQueue:
    """
    SQLite-based task queue with WAL mode for optimal performance.
    
    Designed to maintain memory usage under 50MB while providing reliable
    task persistence and efficient dependency resolution.
    """
    
    def __init__(self, db_path: str = "data/task_queue.db"):
        """
        Initialize the SQLite task queue.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize_database()
        
    def _initialize_database(self) -> None:
        """Initialize the database schema with optimal WAL configuration."""
        with self._get_connection() as conn:
            # Configure SQLite for optimal performance with memory constraints
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=2000")  # ~8MB cache
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping
            conn.execute("PRAGMA busy_timeout=5000")  # 5 second timeout
            
            # Create tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    retry_count INTEGER DEFAULT 0,
                    dependencies TEXT,  -- JSON array
                    input_data TEXT,    -- JSON serialized NodeInput
                    output_data TEXT,   -- JSON serialized NodeOutput
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    INDEX idx_status_priority (status, priority DESC),
                    INDEX idx_workflow_id (workflow_id),
                    INDEX idx_created_at (created_at)
                )
            """)
            
            # Create workflow contexts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_contexts (
                    workflow_id TEXT PRIMARY KEY,
                    current_node_id TEXT,
                    execution_state TEXT,  -- JSON
                    shared_data TEXT,      -- JSON
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise TaskQueueError(f"Database operation failed: {e}")
        finally:
            if conn:
                conn.close()
    
    def add_task(self, task: Task) -> None:
        """
        Add a task to the queue.
        
        Args:
            task: The task to add to the queue.
        """
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO tasks (
                        task_id, node_id, workflow_id, status, priority,
                        max_retries, retry_count, dependencies, input_data,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.task_id,
                    task.node_id,
                    task.workflow_id,
                    task.status.name,
                    task.priority,
                    task.max_retries,
                    task.retry_count,
                    json.dumps(task.dependencies),
                    json.dumps(asdict(task.input_data)),
                    task.created_at.isoformat()
                ))
                conn.commit()
    
    def get_next_ready_task(self) -> Optional[Task]:
        """
        Get the next task that is ready for execution.
        
        Returns the highest priority task whose dependencies are satisfied,
        or None if no tasks are ready.
        """
        with self._lock:
            with self._get_connection() as conn:
                # Get pending tasks ordered by priority
                cursor = conn.execute("""
                    SELECT * FROM tasks 
                    WHERE status = 'PENDING'
                    ORDER BY priority DESC, created_at ASC
                """)
                
                for row in cursor:
                    task = self._row_to_task(row)
                    if self._are_dependencies_satisfied(task, conn):
                        # Mark task as running
                        task.status = NodeStatus.RUNNING
                        task.started_at = datetime.utcnow()
                        self._update_task_status(task, conn)
                        conn.commit()
                        return task
                
                return None
    
    def complete_task(self, task_id: str, output: NodeOutput) -> None:
        """
        Mark a task as completed with the given output.
        
        Args:
            task_id: ID of the task to complete.
            output: The output data from task execution.
        """
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE tasks 
                    SET status = ?, output_data = ?, completed_at = ?
                    WHERE task_id = ?
                """, (
                    NodeStatus.COMPLETED.name,
                    json.dumps(asdict(output)),
                    datetime.utcnow().isoformat(),
                    task_id
                ))
                
                if conn.rowcount == 0:
                    raise TaskNotFoundError(f"Task {task_id} not found")
                
                conn.commit()
    
    def fail_task(self, task_id: str, error_message: str, retry: bool = True) -> bool:
        """
        Mark a task as failed and optionally retry it.
        
        Args:
            task_id: ID of the task that failed.
            error_message: Description of the failure.
            retry: Whether to retry the task if retries are available.
            
        Returns:
            True if the task will be retried, False if permanently failed.
        """
        with self._lock:
            with self._get_connection() as conn:
                # Get current task state
                cursor = conn.execute(
                    "SELECT retry_count, max_retries FROM tasks WHERE task_id = ?",
                    (task_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    raise TaskNotFoundError(f"Task {task_id} not found")
                
                retry_count, max_retries = row['retry_count'], row['max_retries']
                
                if retry and retry_count < max_retries:
                    # Retry the task
                    conn.execute("""
                        UPDATE tasks 
                        SET status = ?, retry_count = ?, started_at = NULL,
                            error_message = ?
                        WHERE task_id = ?
                    """, (
                        NodeStatus.PENDING.name,
                        retry_count + 1,
                        error_message,
                        task_id
                    ))
                    conn.commit()
                    return True
                else:
                    # Permanently failed
                    conn.execute("""
                        UPDATE tasks 
                        SET status = ?, error_message = ?, completed_at = ?
                        WHERE task_id = ?
                    """, (
                        NodeStatus.FAILED.name,
                        error_message,
                        datetime.utcnow().isoformat(),
                        task_id
                    ))
                    conn.commit()
                    return False
    
    def get_workflow_tasks(self, workflow_id: str) -> List[Task]:
        """Get all tasks for a specific workflow."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE workflow_id = ? ORDER BY created_at",
                (workflow_id,)
            )
            return [self._row_to_task(row) for row in cursor]
    
    def save_workflow_context(self, context: WorkflowContext) -> None:
        """Save or update a workflow context."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO workflow_contexts (
                        workflow_id, current_node_id, execution_state,
                        shared_data, started_at, completed_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    context.workflow_id,
                    context.current_node_id,
                    json.dumps(context.execution_state),
                    json.dumps(context.shared_data),
                    context.started_at.isoformat(),
                    context.completed_at.isoformat() if context.completed_at else None,
                    context.status.name
                ))
                conn.commit()
    
    def get_workflow_context(self, workflow_id: str) -> Optional[WorkflowContext]:
        """Get a workflow context by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_contexts WHERE workflow_id = ?",
                (workflow_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return WorkflowContext(
                workflow_id=row['workflow_id'],
                current_node_id=row['current_node_id'],
                execution_state=json.loads(row['execution_state'] or '{}'),
                shared_data=json.loads(row['shared_data'] or '{}'),
                started_at=datetime.fromisoformat(row['started_at']),
                completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                status=NodeStatus[row['status']]
            )
    
    def cleanup_old_tasks(self, older_than_days: int = 7) -> int:
        """
        Clean up completed tasks older than the specified number of days.
        
        Args:
            older_than_days: Remove tasks completed more than this many days ago.
            
        Returns:
            Number of tasks removed.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM tasks 
                    WHERE status IN ('COMPLETED', 'FAILED') 
                    AND completed_at < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                # Also vacuum the database to reclaim space
                conn.execute("VACUUM")
                
                return deleted_count
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get statistics about the current queue state."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM tasks 
                GROUP BY status
            """)
            
            stats = {status.name: 0 for status in NodeStatus}
            stats.update({row['status']: row['count'] for row in cursor})
            
            return stats
    
    def _are_dependencies_satisfied(self, task: Task, conn: sqlite3.Connection) -> bool:
        """Check if all dependencies for a task are satisfied."""
        if not task.dependencies:
            return True
        
        placeholders = ','.join('?' * len(task.dependencies))
        cursor = conn.execute(f"""
            SELECT COUNT(*) as incomplete_count
            FROM tasks 
            WHERE task_id IN ({placeholders}) 
            AND status != 'COMPLETED'
        """, task.dependencies)
        
        result = cursor.fetchone()
        return result['incomplete_count'] == 0
    
    def _update_task_status(self, task: Task, conn: sqlite3.Connection) -> None:
        """Update task status in the database."""
        conn.execute("""
            UPDATE tasks 
            SET status = ?, started_at = ?
            WHERE task_id = ?
        """, (
            task.status.name,
            task.started_at.isoformat() if task.started_at else None,
            task.task_id
        ))
    
    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert a database row to a Task object."""
        task = Task(
            task_id=row['task_id'],
            node_id=row['node_id'],
            workflow_id=row['workflow_id'],
            input_data=NodeInput(**json.loads(row['input_data'])),
            dependencies=json.loads(row['dependencies'] or '[]'),
            priority=row['priority'],
            max_retries=row['max_retries']
        )
        
        task.retry_count = row['retry_count']
        task.status = NodeStatus[row['status']]
        task.created_at = datetime.fromisoformat(row['created_at'])
        task.error_message = row['error_message']
        
        if row['started_at']:
            task.started_at = datetime.fromisoformat(row['started_at'])
        
        if row['completed_at']:
            task.completed_at = datetime.fromisoformat(row['completed_at'])
        
        if row['output_data']:
            output_dict = json.loads(row['output_data'])
            # Reconstruct NodeOutput with proper enum handling
            output_dict['status'] = NodeStatus[output_dict['status']]
            output_dict['timestamp'] = datetime.fromisoformat(output_dict['timestamp'])
            task.output_data = NodeOutput(**output_dict)
        
        return task


def create_task_id() -> str:
    """Generate a unique task ID."""
    return str(uuid4())