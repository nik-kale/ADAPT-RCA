"""
Runbook definitions for automated remediation.

A runbook is a playbook containing steps to resolve a specific type of incident.
Runbooks can include conditions, rollback steps, and approval requirements.

Classes:
    Runbook: Remediation playbook
    RunbookStep: Individual remediation step
    RunbookCondition: Conditional logic for step execution

Example:
    >>> from adapt_rca.remediation import Runbook, RunbookStep
    >>> from adapt_rca.remediation.actions import RestartServiceAction
    >>>
    >>> # Create runbook for high error rate
    >>> runbook = Runbook(
    ...     name="high-error-rate-remediation",
    ...     description="Restart service when error rate is high",
    ...     trigger_conditions={"error_rate_threshold": 0.1}
    ... )
    >>>
    >>> # Add remediation step
    >>> runbook.add_step(RunbookStep(
    ...     name="restart-service",
    ...     action=RestartServiceAction(service_name="api-gateway"),
    ...     timeout=60
    ... ))
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Status of runbook step execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


@dataclass
class RunbookCondition:
    """
    Condition for step execution.

    Conditions determine whether a step should be executed based
    on incident context or previous step results.
    """

    field: str  # Field to check (e.g., "service", "error_rate")
    operator: str  # Operator: "==", "!=", ">", "<", ">=", "<=", "contains"
    value: Any  # Expected value
    description: Optional[str] = None

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate condition against context.

        Args:
            context: Incident or execution context

        Returns:
            True if condition is met
        """
        if self.field not in context:
            logger.debug(f"Field '{self.field}' not in context, condition failed")
            return False

        actual_value = context[self.field]

        try:
            if self.operator == "==":
                result = actual_value == self.value
            elif self.operator == "!=":
                result = actual_value != self.value
            elif self.operator == ">":
                result = float(actual_value) > float(self.value)
            elif self.operator == "<":
                result = float(actual_value) < float(self.value)
            elif self.operator == ">=":
                result = float(actual_value) >= float(self.value)
            elif self.operator == "<=":
                result = float(actual_value) <= float(self.value)
            elif self.operator == "contains":
                result = self.value in actual_value
            else:
                logger.error(f"Unknown operator: {self.operator}")
                return False

            logger.debug(
                f"Condition: {self.field} {self.operator} {self.value} "
                f"(actual: {actual_value}) = {result}"
            )
            return result

        except (TypeError, ValueError) as e:
            logger.error(f"Error evaluating condition: {e}")
            return False


@dataclass
class RunbookStep:
    """
    Individual step in a runbook.

    Each step represents an action to perform as part of remediation.
    """

    name: str
    action: Any  # RemediationAction instance
    description: Optional[str] = None
    conditions: List[RunbookCondition] = field(default_factory=list)
    timeout: int = 300  # Timeout in seconds
    retry_count: int = 0  # Number of retries on failure
    retry_delay: int = 5  # Delay between retries (seconds)
    rollback_action: Optional[Any] = None  # Action to execute on rollback
    require_approval: bool = False  # Whether step requires human approval

    def should_execute(self, context: Dict[str, Any]) -> bool:
        """
        Check if step should be executed based on conditions.

        Args:
            context: Execution context

        Returns:
            True if all conditions are met
        """
        if not self.conditions:
            return True

        # All conditions must be true
        return all(condition.evaluate(context) for condition in self.conditions)


@dataclass
class Runbook:
    """
    Remediation runbook (playbook).

    A runbook defines a series of steps to automatically remediate
    a specific type of incident.

    Example:
        >>> runbook = Runbook(
        ...     name="database-connection-exhaustion",
        ...     description="Remediate DB connection pool issues"
        ... )
        >>> runbook.add_step(RunbookStep(
        ...     name="scale-db-pool",
        ...     action=ScaleServiceAction(service="db-pool", target_size=20)
        ... ))
    """

    name: str
    description: str
    trigger_conditions: Dict[str, Any] = field(default_factory=dict)
    steps: List[RunbookStep] = field(default_factory=list)
    require_approval: bool = False  # Require approval before execution
    max_execution_time: int = 1800  # Max total execution time (seconds)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: RunbookStep) -> None:
        """Add a step to the runbook."""
        self.steps.append(step)
        self.updated_at = datetime.now()
        logger.debug(f"Added step '{step.name}' to runbook '{self.name}'")

    def add_condition(
        self,
        field: str,
        operator: str,
        value: Any,
        description: Optional[str] = None
    ) -> RunbookCondition:
        """
        Add a trigger condition to the runbook.

        Args:
            field: Field to check
            operator: Comparison operator
            value: Expected value
            description: Human-readable description

        Returns:
            Created condition
        """
        condition = RunbookCondition(
            field=field,
            operator=operator,
            value=value,
            description=description
        )

        if "conditions" not in self.trigger_conditions:
            self.trigger_conditions["conditions"] = []

        self.trigger_conditions["conditions"].append(condition)
        self.updated_at = datetime.now()

        return condition

    def should_trigger(self, incident_context: Dict[str, Any]) -> bool:
        """
        Check if runbook should be triggered for incident.

        Args:
            incident_context: Incident information

        Returns:
            True if runbook should be executed
        """
        if "conditions" not in self.trigger_conditions:
            # No specific conditions, can always trigger
            return True

        conditions = self.trigger_conditions["conditions"]

        # All trigger conditions must be met
        return all(
            condition.evaluate(incident_context)
            for condition in conditions
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert runbook to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "trigger_conditions": self.trigger_conditions,
            "steps": [
                {
                    "name": step.name,
                    "description": step.description,
                    "action_type": type(step.action).__name__,
                    "timeout": step.timeout,
                    "retry_count": step.retry_count,
                    "require_approval": step.require_approval
                }
                for step in self.steps
            ],
            "require_approval": self.require_approval,
            "max_execution_time": self.max_execution_time,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }

    def validate(self) -> List[str]:
        """
        Validate runbook configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not self.name:
            errors.append("Runbook must have a name")

        if not self.steps:
            errors.append("Runbook must have at least one step")

        # Validate steps
        for i, step in enumerate(self.steps):
            if not step.name:
                errors.append(f"Step {i} must have a name")

            if step.action is None:
                errors.append(f"Step {i} ('{step.name}') must have an action")

            if step.timeout <= 0:
                errors.append(f"Step {i} ('{step.name}') timeout must be positive")

            if step.retry_count < 0:
                errors.append(f"Step {i} ('{step.name}') retry_count cannot be negative")

        return errors


class RunbookLibrary:
    """
    Library of runbooks.

    Manages collection of runbooks and matches them to incidents.
    """

    def __init__(self):
        """Initialize runbook library."""
        self.runbooks: Dict[str, Runbook] = {}

    def register(self, runbook: Runbook) -> None:
        """
        Register a runbook in the library.

        Args:
            runbook: Runbook to register

        Raises:
            ValueError: If runbook has validation errors
        """
        # Validate runbook
        errors = runbook.validate()
        if errors:
            raise ValueError(f"Invalid runbook: {', '.join(errors)}")

        self.runbooks[runbook.name] = runbook
        logger.info(f"Registered runbook: '{runbook.name}' with {len(runbook.steps)} steps")

    def get(self, name: str) -> Optional[Runbook]:
        """Get runbook by name."""
        return self.runbooks.get(name)

    def find_matching_runbooks(
        self,
        incident_context: Dict[str, Any]
    ) -> List[Runbook]:
        """
        Find runbooks that match the incident.

        Args:
            incident_context: Incident information

        Returns:
            List of matching runbooks
        """
        matching = []

        for runbook in self.runbooks.values():
            if runbook.should_trigger(incident_context):
                matching.append(runbook)
                logger.debug(f"Runbook '{runbook.name}' matches incident")

        logger.info(
            f"Found {len(matching)} matching runbooks for incident"
        )

        return matching

    def list_runbooks(self) -> List[str]:
        """List all runbook names."""
        return list(self.runbooks.keys())

    def remove(self, name: str) -> bool:
        """
        Remove runbook from library.

        Args:
            name: Runbook name

        Returns:
            True if removed, False if not found
        """
        if name in self.runbooks:
            del self.runbooks[name]
            logger.info(f"Removed runbook: '{name}'")
            return True

        return False
