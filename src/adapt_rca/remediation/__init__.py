"""
Automated remediation engine for ADAPT-RCA.

This module provides automated incident remediation capabilities including:
- Runbook execution
- Action plugins (restart, scale, rollback, etc.)
- Approval workflows
- Remediation history tracking

Classes:
    RemediationEngine: Core remediation orchestration
    Runbook: Remediation playbook definition
    RemediationAction: Base class for actions
    RemediationResult: Result of remediation execution
"""

from .engine import RemediationEngine, RemediationResult, ExecutionStatus
from .runbook import Runbook, RunbookStep, RunbookCondition
from .actions import (
    RemediationAction,
    RestartServiceAction,
    ScaleServiceAction,
    RollbackDeploymentAction,
    RunCommandAction,
    WebhookAction
)

__all__ = [
    "RemediationEngine",
    "RemediationResult",
    "ExecutionStatus",
    "Runbook",
    "RunbookStep",
    "RunbookCondition",
    "RemediationAction",
    "RestartServiceAction",
    "ScaleServiceAction",
    "RollbackDeploymentAction",
    "RunCommandAction",
    "WebhookAction",
]
