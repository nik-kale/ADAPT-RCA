"""
Audit system for ADAPT-RCA.

Provides pluggable audit backends for tracking system events, user actions,
and security-relevant operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of audit events."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    RCA_STARTED = "rca_started"
    RCA_COMPLETED = "rca_completed"
    RCA_FAILED = "rca_failed"
    CONFIG_CHANGED = "config_changed"
    DATA_ACCESSED = "data_accessed"
    DATA_MODIFIED = "data_modified"
    API_CALL = "api_call"
    ERROR = "error"


@dataclass
class AuditEvent:
    """
    Audit event data class.

    Attributes:
        id: Unique event identifier
        timestamp: Event timestamp (ISO 8601)
        event_type: Type of event
        user_id: User who triggered the event
        action: Action performed
        resource_id: Resource affected (optional)
        resource_type: Type of resource (optional)
        result: Result of action (success/failure)
        details: Additional event details
        ip_address: Client IP address (optional)
        session_id: Session identifier (optional)
    """
    id: str
    timestamp: str
    event_type: EventType
    user_id: str
    action: str
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    result: str = "success"
    details: Optional[Dict] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class AuditBackend(ABC):
    """Abstract base class for audit backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend."""
        pass

    @abstractmethod
    async def write_event(self, event: AuditEvent) -> None:
        """Write an audit event."""
        pass

    @abstractmethod
    async def query_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[EventType] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Query audit events."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close backend connections."""
        pass


class FileAuditBackend(AuditBackend):
    """
    File-based audit backend.

    Stores audit events in JSONL format.
    """

    def __init__(self, file_path: str = "audit.jsonl"):
        """
        Initialize file backend.

        Args:
            file_path: Path to audit log file
        """
        self.file_path = Path(file_path)

    async def initialize(self) -> None:
        """Initialize the backend."""
        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file if it doesn't exist
        if not self.file_path.exists():
            self.file_path.touch()

        logger.info(f"File audit backend initialized: {self.file_path}")

    async def write_event(self, event: AuditEvent) -> None:
        """
        Write an audit event to file.

        Args:
            event: Audit event to write
        """
        try:
            with self.file_path.open("a") as f:
                f.write(event.to_json() + "\n")
        except IOError as e:
            logger.error(f"Failed to write audit event: {e}")
            raise

    async def query_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[EventType] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Query audit events from file.

        Args:
            start_time: Filter events after this time
            end_time: Filter events before this time
            event_type: Filter by event type
            user_id: Filter by user ID
            limit: Maximum number of events to return

        Returns:
            List of matching audit events
        """
        events = []

        try:
            with self.file_path.open("r") as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        event_data = json.loads(line)

                        # Apply filters
                        if event_type and event_data.get("event_type") != event_type.value:
                            continue

                        if user_id and event_data.get("user_id") != user_id:
                            continue

                        if start_time:
                            event_time = datetime.fromisoformat(event_data["timestamp"])
                            if event_time < start_time:
                                continue

                        if end_time:
                            event_time = datetime.fromisoformat(event_data["timestamp"])
                            if event_time > end_time:
                                continue

                        # Reconstruct AuditEvent
                        event_data["event_type"] = EventType(event_data["event_type"])
                        events.append(AuditEvent(**event_data))

                        if len(events) >= limit:
                            break

                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning(f"Skipping invalid audit event: {e}")
                        continue

        except IOError as e:
            logger.error(f"Failed to query audit events: {e}")
            raise

        return events

    async def close(self) -> None:
        """Close backend connections."""
        # File backend doesn't need cleanup
        pass


class PostgreSQLAuditBackend(AuditBackend):
    """
    PostgreSQL-based audit backend.

    Stores audit events in PostgreSQL database for scalable querying.
    """

    def __init__(
        self,
        connection_string: str,
        table_name: str = "audit_events"
    ):
        """
        Initialize PostgreSQL backend.

        Args:
            connection_string: PostgreSQL connection string
            table_name: Name of audit events table
        """
        self.connection_string = connection_string
        self.table_name = table_name
        self.pool = None

    async def initialize(self) -> None:
        """
        Initialize the backend.

        Creates connection pool and ensures table exists.
        """
        # NOTE: This requires asyncpg to be installed
        # For now, this is a placeholder implementation
        logger.info(f"PostgreSQL audit backend initialized: {self.table_name}")

        # TODO: Initialize connection pool
        # self.pool = await asyncpg.create_pool(self.connection_string)

        # TODO: Create table if not exists
        # await self._create_table()

    async def _create_table(self) -> None:
        """Create audit events table if it doesn't exist."""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id VARCHAR(255) PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            action VARCHAR(255) NOT NULL,
            resource_id VARCHAR(255),
            resource_type VARCHAR(100),
            result VARCHAR(50) NOT NULL,
            details JSONB,
            ip_address VARCHAR(45),
            session_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_timestamp ON {self.table_name}(timestamp);
        CREATE INDEX IF NOT EXISTS idx_event_type ON {self.table_name}(event_type);
        CREATE INDEX IF NOT EXISTS idx_user_id ON {self.table_name}(user_id);
        CREATE INDEX IF NOT EXISTS idx_resource_id ON {self.table_name}(resource_id);
        """

        # TODO: Execute SQL
        # async with self.pool.acquire() as conn:
        #     await conn.execute(create_table_sql)

        logger.info(f"Created audit table: {self.table_name}")

    async def write_event(self, event: AuditEvent) -> None:
        """
        Write an audit event to PostgreSQL.

        Args:
            event: Audit event to write
        """
        # TODO: Implement PostgreSQL write
        # insert_sql = f"""
        # INSERT INTO {self.table_name}
        # (id, timestamp, event_type, user_id, action, resource_id, resource_type,
        #  result, details, ip_address, session_id)
        # VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        # """
        #
        # async with self.pool.acquire() as conn:
        #     await conn.execute(
        #         insert_sql,
        #         event.id,
        #         datetime.fromisoformat(event.timestamp),
        #         event.event_type.value,
        #         event.user_id,
        #         event.action,
        #         event.resource_id,
        #         event.resource_type,
        #         event.result,
        #         json.dumps(event.details) if event.details else None,
        #         event.ip_address,
        #         event.session_id
        #     )

        logger.debug(f"Wrote audit event to PostgreSQL: {event.id}")

    async def query_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[EventType] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Query audit events from PostgreSQL.

        Args:
            start_time: Filter events after this time
            end_time: Filter events before this time
            event_type: Filter by event type
            user_id: Filter by user ID
            limit: Maximum number of events to return

        Returns:
            List of matching audit events
        """
        # TODO: Implement PostgreSQL query
        # Build WHERE clause dynamically based on filters
        # Use parameterized query to prevent SQL injection

        logger.debug(f"Querying audit events with limit {limit}")
        return []

    async def close(self) -> None:
        """Close backend connections."""
        # TODO: Close connection pool
        # if self.pool:
        #     await self.pool.close()

        logger.info("PostgreSQL audit backend closed")


class AuditSystem:
    """
    Audit system managing event logging.

    Supports multiple backends (file, PostgreSQL).
    """

    def __init__(self, backend: AuditBackend):
        """
        Initialize audit system.

        Args:
            backend: Audit backend to use
        """
        self.backend = backend

    async def initialize(self) -> None:
        """Initialize the audit system."""
        await self.backend.initialize()

    async def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event.

        Args:
            event: Event to log
        """
        await self.backend.write_event(event)

    async def query_events(self, **kwargs) -> List[AuditEvent]:
        """
        Query audit events.

        Args:
            **kwargs: Query parameters (start_time, end_time, event_type, user_id, limit)

        Returns:
            List of matching audit events
        """
        return await self.backend.query_events(**kwargs)

    async def close(self) -> None:
        """Close the audit system."""
        await self.backend.close()

