"""
Remediation actions for ADAPT-RCA.

This module provides various remediation actions that can be executed
as part of runbooks. Actions are plugins that can be extended.

Classes:
    RemediationAction: Base class for all actions
    RestartServiceAction: Restart a service/container
    ScaleServiceAction: Scale service instances
    RollbackDeploymentAction: Rollback to previous deployment
    RunCommandAction: Execute custom command
    WebhookAction: Call external webhook

Example:
    >>> from adapt_rca.remediation.actions import RestartServiceAction
    >>> action = RestartServiceAction(service_name="api-gateway")
    >>> result = action.execute(context={})
"""

import logging
import subprocess
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ActionStatus(Enum):
    """Status of action execution."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class ActionResult:
    """Result of action execution."""

    status: ActionStatus
    message: str
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "message": self.message,
            "output": self.output,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp.isoformat()
        }


class RemediationAction(ABC):
    """
    Base class for remediation actions.

    All remediation actions must inherit from this class and
    implement the execute() method.
    """

    def __init__(self, dry_run: bool = False):
        """
        Initialize action.

        Args:
            dry_run: If True, simulate action without actually executing
        """
        self.dry_run = dry_run

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> ActionResult:
        """
        Execute the remediation action.

        Args:
            context: Execution context with incident information

        Returns:
            ActionResult with execution status
        """
        pass

    @abstractmethod
    def rollback(self, context: Dict[str, Any]) -> ActionResult:
        """
        Rollback the action if needed.

        Args:
            context: Execution context

        Returns:
            ActionResult with rollback status
        """
        pass

    @abstractmethod
    def validate(self) -> Optional[str]:
        """
        Validate action configuration.

        Returns:
            Error message if invalid, None if valid
        """
        pass

    def __str__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(dry_run={self.dry_run})"


class RestartServiceAction(RemediationAction):
    """
    Action to restart a service or container.

    Supports various platforms:
    - Docker containers
    - Kubernetes pods
    - Systemd services
    - Custom restart commands

    Example:
        >>> action = RestartServiceAction(
        ...     service_name="api-gateway",
        ...     platform="docker"
        ... )
        >>> result = action.execute(context={})
    """

    def __init__(
        self,
        service_name: str,
        platform: str = "docker",  # docker, kubernetes, systemd, custom
        namespace: Optional[str] = None,  # For Kubernetes
        custom_command: Optional[str] = None,
        dry_run: bool = False
    ):
        """Initialize restart action."""
        super().__init__(dry_run=dry_run)
        self.service_name = service_name
        self.platform = platform
        self.namespace = namespace
        self.custom_command = custom_command

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute service restart."""
        start_time = datetime.now()

        try:
            if self.dry_run:
                message = f"[DRY RUN] Would restart {self.service_name} ({self.platform})"
                logger.info(message)
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=message,
                    duration_seconds=0.0
                )

            # Build restart command based on platform
            if self.platform == "docker":
                command = f"docker restart {self.service_name}"

            elif self.platform == "kubernetes":
                ns_flag = f"-n {self.namespace}" if self.namespace else ""
                command = f"kubectl rollout restart deployment/{self.service_name} {ns_flag}"

            elif self.platform == "systemd":
                command = f"sudo systemctl restart {self.service_name}"

            elif self.platform == "custom" and self.custom_command:
                command = self.custom_command

            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Unsupported platform: {self.platform}",
                    error="Invalid platform configuration"
                )

            # Execute command
            logger.info(f"Executing restart: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=f"Successfully restarted {self.service_name}",
                    output=result.stdout,
                    duration_seconds=duration
                )
            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Failed to restart {self.service_name}",
                    error=result.stderr,
                    duration_seconds=duration
                )

        except subprocess.TimeoutExpired:
            return ActionResult(
                status=ActionStatus.TIMEOUT,
                message=f"Restart command timed out for {self.service_name}",
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

        except Exception as e:
            return ActionResult(
                status=ActionStatus.FAILED,
                message=f"Error restarting {self.service_name}: {str(e)}",
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

    def rollback(self, context: Dict[str, Any]) -> ActionResult:
        """Rollback is not applicable for restart."""
        return ActionResult(
            status=ActionStatus.SKIPPED,
            message="Rollback not applicable for restart action"
        )

    def validate(self) -> Optional[str]:
        """Validate action configuration."""
        if not self.service_name:
            return "Service name is required"

        if self.platform == "custom" and not self.custom_command:
            return "Custom command required for 'custom' platform"

        return None


class ScaleServiceAction(RemediationAction):
    """
    Action to scale a service (increase/decrease instances).

    Supports:
    - Kubernetes deployments
    - Docker Swarm services
    - AWS ECS services
    - Custom scaling commands

    Example:
        >>> action = ScaleServiceAction(
        ...     service_name="api-gateway",
        ...     target_replicas=5,
        ...     platform="kubernetes"
        ... )
    """

    def __init__(
        self,
        service_name: str,
        target_replicas: int,
        platform: str = "kubernetes",
        namespace: Optional[str] = None,
        custom_command: Optional[str] = None,
        dry_run: bool = False
    ):
        """Initialize scale action."""
        super().__init__(dry_run=dry_run)
        self.service_name = service_name
        self.target_replicas = target_replicas
        self.platform = platform
        self.namespace = namespace
        self.custom_command = custom_command
        self.previous_replicas: Optional[int] = None

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute service scaling."""
        start_time = datetime.now()

        try:
            if self.dry_run:
                message = (
                    f"[DRY RUN] Would scale {self.service_name} "
                    f"to {self.target_replicas} replicas"
                )
                logger.info(message)
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=message,
                    duration_seconds=0.0
                )

            # Get current replica count for rollback
            # (simplified - in production, query actual state)
            self.previous_replicas = context.get("current_replicas", 1)

            # Build scale command
            if self.platform == "kubernetes":
                ns_flag = f"-n {self.namespace}" if self.namespace else ""
                command = (
                    f"kubectl scale deployment/{self.service_name} "
                    f"--replicas={self.target_replicas} {ns_flag}"
                )

            elif self.platform == "docker-swarm":
                command = (
                    f"docker service scale {self.service_name}={self.target_replicas}"
                )

            elif self.platform == "custom" and self.custom_command:
                command = self.custom_command.format(
                    service=self.service_name,
                    replicas=self.target_replicas
                )

            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Unsupported platform: {self.platform}"
                )

            # Execute command
            logger.info(f"Executing scale: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=(
                        f"Successfully scaled {self.service_name} "
                        f"to {self.target_replicas} replicas"
                    ),
                    output=result.stdout,
                    duration_seconds=duration
                )
            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Failed to scale {self.service_name}",
                    error=result.stderr,
                    duration_seconds=duration
                )

        except Exception as e:
            return ActionResult(
                status=ActionStatus.FAILED,
                message=f"Error scaling {self.service_name}: {str(e)}",
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

    def rollback(self, context: Dict[str, Any]) -> ActionResult:
        """Rollback to previous replica count."""
        if self.previous_replicas is None:
            return ActionResult(
                status=ActionStatus.SKIPPED,
                message="No previous replica count available"
            )

        # Create reverse scale action
        reverse_action = ScaleServiceAction(
            service_name=self.service_name,
            target_replicas=self.previous_replicas,
            platform=self.platform,
            namespace=self.namespace,
            dry_run=self.dry_run
        )

        return reverse_action.execute(context)

    def validate(self) -> Optional[str]:
        """Validate action configuration."""
        if not self.service_name:
            return "Service name is required"

        if self.target_replicas < 0:
            return "Target replicas must be non-negative"

        return None


class RollbackDeploymentAction(RemediationAction):
    """
    Action to rollback a deployment to previous version.

    Supports:
    - Kubernetes deployments
    - Docker images
    - Custom rollback commands

    Example:
        >>> action = RollbackDeploymentAction(
        ...     service_name="api-gateway",
        ...     platform="kubernetes"
        ... )
    """

    def __init__(
        self,
        service_name: str,
        platform: str = "kubernetes",
        namespace: Optional[str] = None,
        revision: Optional[int] = None,  # Specific revision to rollback to
        custom_command: Optional[str] = None,
        dry_run: bool = False
    ):
        """Initialize rollback action."""
        super().__init__(dry_run=dry_run)
        self.service_name = service_name
        self.platform = platform
        self.namespace = namespace
        self.revision = revision
        self.custom_command = custom_command

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute deployment rollback."""
        start_time = datetime.now()

        try:
            if self.dry_run:
                message = f"[DRY RUN] Would rollback {self.service_name}"
                logger.info(message)
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=message,
                    duration_seconds=0.0
                )

            # Build rollback command
            if self.platform == "kubernetes":
                ns_flag = f"-n {self.namespace}" if self.namespace else ""
                revision_flag = f"--to-revision={self.revision}" if self.revision else ""
                command = (
                    f"kubectl rollout undo deployment/{self.service_name} "
                    f"{revision_flag} {ns_flag}"
                )

            elif self.platform == "custom" and self.custom_command:
                command = self.custom_command

            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Unsupported platform: {self.platform}"
                )

            # Execute command
            logger.info(f"Executing rollback: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=f"Successfully rolled back {self.service_name}",
                    output=result.stdout,
                    duration_seconds=duration
                )
            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Failed to rollback {self.service_name}",
                    error=result.stderr,
                    duration_seconds=duration
                )

        except Exception as e:
            return ActionResult(
                status=ActionStatus.FAILED,
                message=f"Error rolling back {self.service_name}: {str(e)}",
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

    def rollback(self, context: Dict[str, Any]) -> ActionResult:
        """Rollback of a rollback would be rolling forward."""
        return ActionResult(
            status=ActionStatus.SKIPPED,
            message="Cannot rollback a rollback action"
        )

    def validate(self) -> Optional[str]:
        """Validate action configuration."""
        if not self.service_name:
            return "Service name is required"

        return None


class RunCommandAction(RemediationAction):
    """
    Action to run a custom command.

    Allows execution of arbitrary commands for flexible remediation.

    Example:
        >>> action = RunCommandAction(
        ...     command="kubectl delete pod -l app=cache",
        ...     description="Clear cache pods"
        ... )
    """

    def __init__(
        self,
        command: str,
        description: Optional[str] = None,
        timeout: int = 60,
        dry_run: bool = False
    ):
        """Initialize command action."""
        super().__init__(dry_run=dry_run)
        self.command = command
        self.description = description or command
        self.timeout = timeout

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute custom command."""
        start_time = datetime.now()

        try:
            if self.dry_run:
                message = f"[DRY RUN] Would run: {self.command}"
                logger.info(message)
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=message,
                    duration_seconds=0.0
                )

            # Execute command
            logger.info(f"Executing command: {self.command}")
            result = subprocess.run(
                self.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=f"Command executed successfully: {self.description}",
                    output=result.stdout,
                    duration_seconds=duration
                )
            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Command failed: {self.description}",
                    error=result.stderr,
                    output=result.stdout,
                    duration_seconds=duration
                )

        except subprocess.TimeoutExpired:
            return ActionResult(
                status=ActionStatus.TIMEOUT,
                message=f"Command timed out after {self.timeout}s",
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

        except Exception as e:
            return ActionResult(
                status=ActionStatus.FAILED,
                message=f"Error executing command: {str(e)}",
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

    def rollback(self, context: Dict[str, Any]) -> ActionResult:
        """No rollback for generic commands."""
        return ActionResult(
            status=ActionStatus.SKIPPED,
            message="Rollback not supported for custom commands"
        )

    def validate(self) -> Optional[str]:
        """Validate action configuration."""
        if not self.command:
            return "Command is required"

        if self.timeout <= 0:
            return "Timeout must be positive"

        return None


class WebhookAction(RemediationAction):
    """
    Action to call an external webhook.

    Useful for triggering external remediation systems or notifications.

    Example:
        >>> action = WebhookAction(
        ...     url="https://api.example.com/remediate",
        ...     method="POST",
        ...     headers={"Authorization": "Bearer token"}
        ... )
    """

    def __init__(
        self,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        dry_run: bool = False
    ):
        """Initialize webhook action."""
        super().__init__(dry_run=dry_run)
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.payload = payload or {}
        self.timeout = timeout

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute webhook call."""
        start_time = datetime.now()

        try:
            if self.dry_run:
                message = f"[DRY RUN] Would call webhook: {self.method} {self.url}"
                logger.info(message)
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=message,
                    duration_seconds=0.0
                )

            # Merge context into payload
            request_payload = {**self.payload, "context": context}

            # Make HTTP request
            logger.info(f"Calling webhook: {self.method} {self.url}")
            response = requests.request(
                method=self.method,
                url=self.url,
                json=request_payload,
                headers=self.headers,
                timeout=self.timeout
            )

            duration = (datetime.now() - start_time).total_seconds()

            if 200 <= response.status_code < 300:
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=f"Webhook call successful: {response.status_code}",
                    output=response.text,
                    duration_seconds=duration
                )
            else:
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Webhook returned error: {response.status_code}",
                    error=response.text,
                    duration_seconds=duration
                )

        except requests.Timeout:
            return ActionResult(
                status=ActionStatus.TIMEOUT,
                message=f"Webhook call timed out after {self.timeout}s",
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

        except Exception as e:
            return ActionResult(
                status=ActionStatus.FAILED,
                message=f"Error calling webhook: {str(e)}",
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

    def rollback(self, context: Dict[str, Any]) -> ActionResult:
        """No rollback for webhooks."""
        return ActionResult(
            status=ActionStatus.SKIPPED,
            message="Rollback not supported for webhook actions"
        )

    def validate(self) -> Optional[str]:
        """Validate action configuration."""
        if not self.url:
            return "URL is required"

        if self.method not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            return f"Invalid HTTP method: {self.method}"

        if self.timeout <= 0:
            return "Timeout must be positive"

        return None
