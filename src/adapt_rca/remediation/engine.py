"""
Remediation engine for ADAPT-RCA.

Orchestrates execution of remediation runbooks including:
- Runbook selection based on incident
- Step execution with retries
- Approval workflows
- Rollback on failure
- Execution history tracking

Classes:
    RemediationEngine: Core remediation orchestrator
    RemediationResult: Execution result
    ExecutionStatus: Execution status enum

Example:
    >>> from adapt_rca.remediation import RemediationEngine, Runbook
    >>> engine = RemediationEngine()
    >>>
    >>> # Register runbook
    >>> engine.register_runbook(runbook)
    >>>
    >>> # Execute remediation
    >>> result = engine.remediate(incident_context, auto_approve=False)
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .runbook import Runbook, RunbookStep, RunbookLibrary, StepStatus
from .actions import ActionResult, ActionStatus

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Overall remediation execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Some steps succeeded, some failed
    ROLLED_BACK = "rolled_back"
    PENDING_APPROVAL = "pending_approval"
    CANCELLED = "cancelled"


@dataclass
class StepExecution:
    """Execution record for a single step."""

    step_name: str
    status: StepStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    action_result: Optional[ActionResult] = None
    retry_count: int = 0
    error_message: Optional[str] = None


@dataclass
class RemediationResult:
    """Result of remediation execution."""

    execution_id: str
    runbook_name: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    steps_executed: List[StepExecution] = field(default_factory=list)
    incident_context: Dict[str, Any] = field(default_factory=dict)
    rollback_performed: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "runbook_name": self.runbook_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_seconds": self.total_duration_seconds,
            "steps_executed": [
                {
                    "step_name": step.step_name,
                    "status": step.status.value,
                    "duration_seconds": step.duration_seconds,
                    "retry_count": step.retry_count
                }
                for step in self.steps_executed
            ],
            "rollback_performed": self.rollback_performed,
            "error_message": self.error_message
        }


class RemediationEngine:
    """
    Automated remediation orchestration engine.

    Executes remediation runbooks in response to incidents,
    handling retries, approvals, and rollbacks.

    Example:
        >>> engine = RemediationEngine()
        >>> engine.register_runbook(high_error_rate_runbook)
        >>>
        >>> incident = {
        ...     "service": "api-gateway",
        ...     "error_rate": 0.15,
        ...     "severity": "high"
        ... }
        >>>
        >>> result = engine.remediate(incident, auto_approve=True)
        >>> if result.status == ExecutionStatus.SUCCESS:
        ...     print("Remediation successful!")
    """

    def __init__(
        self,
        dry_run: bool = False,
        enable_rollback: bool = True
    ):
        """
        Initialize remediation engine.

        Args:
            dry_run: If True, simulate actions without executing
            enable_rollback: Whether to rollback on failure
        """
        self.library = RunbookLibrary()
        self.dry_run = dry_run
        self.enable_rollback = enable_rollback

        self.execution_history: List[RemediationResult] = []
        self.pending_approvals: Dict[str, RemediationResult] = {}

        logger.info(
            f"Initialized RemediationEngine "
            f"(dry_run={dry_run}, rollback={enable_rollback})"
        )

    def register_runbook(self, runbook: Runbook) -> None:
        """
        Register a runbook in the engine.

        Args:
            runbook: Runbook to register

        Example:
            >>> runbook = Runbook(name="restart-on-error", ...)
            >>> engine.register_runbook(runbook)
        """
        self.library.register(runbook)

    def remediate(
        self,
        incident_context: Dict[str, Any],
        runbook_name: Optional[str] = None,
        auto_approve: bool = False
    ) -> RemediationResult:
        """
        Execute remediation for an incident.

        Args:
            incident_context: Incident information
            runbook_name: Specific runbook to use (auto-select if None)
            auto_approve: Whether to auto-approve steps requiring approval

        Returns:
            RemediationResult with execution details

        Example:
            >>> incident = {"service": "api", "error_rate": 0.2}
            >>> result = engine.remediate(incident, auto_approve=True)
        """
        execution_id = self._generate_execution_id()
        started_at = datetime.now()

        logger.info(
            f"Starting remediation {execution_id} for incident: {incident_context}"
        )

        # Select runbook
        if runbook_name:
            runbook = self.library.get(runbook_name)
            if runbook is None:
                return self._create_failed_result(
                    execution_id,
                    runbook_name or "unknown",
                    started_at,
                    f"Runbook '{runbook_name}' not found",
                    incident_context
                )
        else:
            matching_runbooks = self.library.find_matching_runbooks(incident_context)

            if not matching_runbooks:
                return self._create_failed_result(
                    execution_id,
                    "none",
                    started_at,
                    "No matching runbooks found for incident",
                    incident_context
                )

            # Use first matching runbook
            runbook = matching_runbooks[0]
            logger.info(f"Selected runbook: '{runbook.name}'")

        # Check if runbook requires approval
        if runbook.require_approval and not auto_approve:
            result = RemediationResult(
                execution_id=execution_id,
                runbook_name=runbook.name,
                status=ExecutionStatus.PENDING_APPROVAL,
                started_at=started_at,
                incident_context=incident_context
            )
            self.pending_approvals[execution_id] = result
            logger.info(f"Remediation {execution_id} pending approval")
            return result

        # Execute runbook
        return self._execute_runbook(
            execution_id,
            runbook,
            incident_context,
            started_at,
            auto_approve
        )

    def approve_remediation(self, execution_id: str) -> RemediationResult:
        """
        Approve and execute a pending remediation.

        Args:
            execution_id: Execution ID from remediate()

        Returns:
            Updated RemediationResult

        Example:
            >>> result = engine.remediate(incident)
            >>> if result.status == ExecutionStatus.PENDING_APPROVAL:
            ...     result = engine.approve_remediation(result.execution_id)
        """
        if execution_id not in self.pending_approvals:
            raise ValueError(f"No pending approval for {execution_id}")

        pending_result = self.pending_approvals.pop(execution_id)

        runbook = self.library.get(pending_result.runbook_name)
        if runbook is None:
            return self._create_failed_result(
                execution_id,
                pending_result.runbook_name,
                pending_result.started_at,
                "Runbook no longer available",
                pending_result.incident_context
            )

        logger.info(f"Executing approved remediation {execution_id}")

        return self._execute_runbook(
            execution_id,
            runbook,
            pending_result.incident_context,
            pending_result.started_at,
            auto_approve=True  # Already approved
        )

    def _execute_runbook(
        self,
        execution_id: str,
        runbook: Runbook,
        incident_context: Dict[str, Any],
        started_at: datetime,
        auto_approve: bool
    ) -> RemediationResult:
        """Execute runbook steps."""
        result = RemediationResult(
            execution_id=execution_id,
            runbook_name=runbook.name,
            status=ExecutionStatus.SUCCESS,
            started_at=started_at,
            incident_context=incident_context
        )

        execution_context = {**incident_context}

        # Execute each step
        for step in runbook.steps:
            # Check if step should be executed
            if not step.should_execute(execution_context):
                logger.info(f"Skipping step '{step.name}' (conditions not met)")
                result.steps_executed.append(StepExecution(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    started_at=datetime.now()
                ))
                continue

            # Check approval requirement
            if step.require_approval and not auto_approve:
                logger.warning(
                    f"Step '{step.name}' requires approval but auto_approve is False. "
                    f"Stopping execution."
                )
                result.status = ExecutionStatus.PENDING_APPROVAL
                break

            # Execute step
            step_result = self._execute_step(step, execution_context)
            result.steps_executed.append(step_result)

            # Check step status
            if step_result.status == StepStatus.FAILED:
                logger.error(f"Step '{step.name}' failed")
                result.status = ExecutionStatus.FAILED
                result.error_message = step_result.error_message

                # Rollback if enabled
                if self.enable_rollback:
                    logger.info("Starting rollback due to failed step")
                    self._rollback(result)
                    result.status = ExecutionStatus.ROLLED_BACK

                break

        # Complete execution
        result.completed_at = datetime.now()
        result.total_duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        # Determine final status
        if result.status == ExecutionStatus.SUCCESS:
            if all(s.status == StepStatus.SUCCESS for s in result.steps_executed):
                result.status = ExecutionStatus.SUCCESS
            else:
                result.status = ExecutionStatus.PARTIAL

        # Store in history
        self.execution_history.append(result)

        logger.info(
            f"Remediation {execution_id} completed with status: {result.status.value}"
        )

        return result

    def _execute_step(
        self,
        step: RunbookStep,
        context: Dict[str, Any]
    ) -> StepExecution:
        """Execute a single runbook step with retries."""
        started_at = datetime.now()
        logger.info(f"Executing step: '{step.name}'")

        action_result = None
        retry_count = 0

        # Execute with retries
        for attempt in range(step.retry_count + 1):
            if attempt > 0:
                retry_count = attempt
                logger.info(
                    f"Retrying step '{step.name}' (attempt {attempt + 1}/{step.retry_count + 1})"
                )
                time.sleep(step.retry_delay)

            # Execute action
            action_result = step.action.execute(context)

            if action_result.status == ActionStatus.SUCCESS:
                break

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        # Determine step status
        if action_result.status == ActionStatus.SUCCESS:
            status = StepStatus.SUCCESS
        elif action_result.status == ActionStatus.TIMEOUT:
            status = StepStatus.FAILED
            logger.error(f"Step '{step.name}' timed out")
        else:
            status = StepStatus.FAILED
            logger.error(f"Step '{step.name}' failed after {retry_count + 1} attempts")

        return StepExecution(
            step_name=step.name,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            action_result=action_result,
            retry_count=retry_count,
            error_message=action_result.error if status == StepStatus.FAILED else None
        )

    def _rollback(self, result: RemediationResult) -> None:
        """Rollback executed steps in reverse order."""
        logger.warning(f"Rolling back {len(result.steps_executed)} steps")

        for step_exec in reversed(result.steps_executed):
            if step_exec.status != StepStatus.SUCCESS:
                continue

            logger.info(f"Rolling back step: '{step_exec.step_name}'")

            # Find corresponding runbook step
            runbook = self.library.get(result.runbook_name)
            if runbook:
                step = next(
                    (s for s in runbook.steps if s.name == step_exec.step_name),
                    None
                )

                if step and step.rollback_action:
                    rollback_result = step.rollback_action.execute(
                        result.incident_context
                    )

                    if rollback_result.status == ActionStatus.SUCCESS:
                        step_exec.status = StepStatus.ROLLED_BACK
                        logger.info(f"Successfully rolled back '{step_exec.step_name}'")
                    else:
                        logger.error(
                            f"Failed to rollback '{step_exec.step_name}': "
                            f"{rollback_result.error}"
                        )

        result.rollback_performed = True

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        import uuid
        return f"rem-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    def _create_failed_result(
        self,
        execution_id: str,
        runbook_name: str,
        started_at: datetime,
        error_message: str,
        incident_context: Dict[str, Any]
    ) -> RemediationResult:
        """Create a failed remediation result."""
        result = RemediationResult(
            execution_id=execution_id,
            runbook_name=runbook_name,
            status=ExecutionStatus.FAILED,
            started_at=started_at,
            completed_at=datetime.now(),
            total_duration_seconds=0.0,
            incident_context=incident_context,
            error_message=error_message
        )

        self.execution_history.append(result)
        logger.error(f"Remediation {execution_id} failed: {error_message}")

        return result

    def get_execution_history(
        self,
        limit: Optional[int] = None
    ) -> List[RemediationResult]:
        """
        Get remediation execution history.

        Args:
            limit: Maximum number of results (most recent first)

        Returns:
            List of RemediationResult

        Example:
            >>> history = engine.get_execution_history(limit=10)
            >>> for result in history:
            ...     print(f"{result.execution_id}: {result.status.value}")
        """
        history = sorted(
            self.execution_history,
            key=lambda r: r.started_at,
            reverse=True
        )

        if limit:
            history = history[:limit]

        return history

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get remediation statistics.

        Returns:
            Statistics dictionary

        Example:
            >>> stats = engine.get_statistics()
            >>> print(f"Success rate: {stats['success_rate']:.1%}")
        """
        if not self.execution_history:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_duration_seconds": 0.0
            }

        total = len(self.execution_history)
        successful = sum(
            1 for r in self.execution_history
            if r.status == ExecutionStatus.SUCCESS
        )

        avg_duration = sum(
            r.total_duration_seconds for r in self.execution_history
        ) / total

        status_counts = {}
        for result in self.execution_history:
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_executions": total,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_duration_seconds": avg_duration,
            "status_counts": status_counts,
            "rollback_count": sum(
                1 for r in self.execution_history if r.rollback_performed
            )
        }
