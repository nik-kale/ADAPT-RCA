"""
Tests for audit system.

Verifies audit event logging and querying.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import uuid

from src.adapt_rca.audit.audit_system import (
    AuditEvent,
    EventType,
    FileAuditBackend,
    PostgreSQLAuditBackend,
    AuditSystem,
)


def create_test_event(event_type: EventType = EventType.API_CALL) -> AuditEvent:
    """Create a test audit event."""
    return AuditEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat(),
        event_type=event_type,
        user_id="test-user",
        action="test_action",
        resource_id="test-resource",
        resource_type="test",
        result="success",
        details={"key": "value"},
        ip_address="127.0.0.1",
        session_id="test-session"
    )


def test_audit_event_creation():
    """Test audit event creation."""
    event = create_test_event()
    
    assert event.id is not None
    assert event.event_type == EventType.API_CALL
    assert event.user_id == "test-user"
    assert event.action == "test_action"


def test_audit_event_to_dict():
    """Test audit event to dictionary conversion."""
    event = create_test_event()
    event_dict = event.to_dict()
    
    assert isinstance(event_dict, dict)
    assert event_dict["id"] == event.id
    assert event_dict["event_type"] == "api_call"
    assert event_dict["user_id"] == event.user_id


def test_audit_event_to_json():
    """Test audit event to JSON conversion."""
    event = create_test_event()
    event_json = event.to_json()
    
    assert isinstance(event_json, str)
    assert event.id in event_json
    assert "api_call" in event_json


@pytest.mark.asyncio
async def test_file_backend_initialize():
    """Test file backend initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        
        await backend.initialize()
        
        assert file_path.exists()


@pytest.mark.asyncio
async def test_file_backend_write_event():
    """Test writing event to file backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        await backend.initialize()
        
        event = create_test_event()
        await backend.write_event(event)
        
        # Verify file contains event
        content = file_path.read_text()
        assert event.id in content
        assert "test-user" in content


@pytest.mark.asyncio
async def test_file_backend_query_events():
    """Test querying events from file backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        await backend.initialize()
        
        # Write multiple events
        events = [create_test_event() for _ in range(5)]
        for event in events:
            await backend.write_event(event)
        
        # Query all events
        queried = await backend.query_events(limit=10)
        assert len(queried) == 5


@pytest.mark.asyncio
async def test_file_backend_query_by_event_type():
    """Test querying events by type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        await backend.initialize()
        
        # Write different event types
        await backend.write_event(create_test_event(EventType.API_CALL))
        await backend.write_event(create_test_event(EventType.RCA_STARTED))
        await backend.write_event(create_test_event(EventType.API_CALL))
        
        # Query API_CALL events
        queried = await backend.query_events(event_type=EventType.API_CALL)
        assert len(queried) == 2
        assert all(e.event_type == EventType.API_CALL for e in queried)


@pytest.mark.asyncio
async def test_file_backend_query_by_user():
    """Test querying events by user ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        await backend.initialize()
        
        # Write events for different users
        event1 = create_test_event()
        event1.user_id = "user1"
        await backend.write_event(event1)
        
        event2 = create_test_event()
        event2.user_id = "user2"
        await backend.write_event(event2)
        
        event3 = create_test_event()
        event3.user_id = "user1"
        await backend.write_event(event3)
        
        # Query user1 events
        queried = await backend.query_events(user_id="user1")
        assert len(queried) == 2
        assert all(e.user_id == "user1" for e in queried)


@pytest.mark.asyncio
async def test_file_backend_query_limit():
    """Test query result limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        await backend.initialize()
        
        # Write 10 events
        for _ in range(10):
            await backend.write_event(create_test_event())
        
        # Query with limit
        queried = await backend.query_events(limit=5)
        assert len(queried) == 5


@pytest.mark.asyncio
async def test_audit_system_log_event():
    """Test audit system event logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        system = AuditSystem(backend)
        
        await system.initialize()
        
        event = create_test_event()
        await system.log_event(event)
        
        # Verify event was logged
        queried = await system.query_events()
        assert len(queried) == 1
        assert queried[0].id == event.id


@pytest.mark.asyncio
async def test_audit_system_query_events():
    """Test audit system event querying."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        system = AuditSystem(backend)
        
        await system.initialize()
        
        # Log multiple events
        for i in range(3):
            event = create_test_event()
            event.user_id = f"user-{i}"
            await system.log_event(event)
        
        # Query events
        queried = await system.query_events(limit=10)
        assert len(queried) == 3


def test_postgresql_backend_initialization():
    """Test PostgreSQL backend initialization."""
    backend = PostgreSQLAuditBackend(
        connection_string="postgresql://localhost/test",
        table_name="audit_events"
    )
    
    assert backend.connection_string == "postgresql://localhost/test"
    assert backend.table_name == "audit_events"


@pytest.mark.asyncio
async def test_postgresql_backend_placeholder():
    """Test PostgreSQL backend placeholder methods."""
    backend = PostgreSQLAuditBackend("postgresql://localhost/test")
    
    # Initialize (should not raise)
    await backend.initialize()
    
    # Write event (placeholder)
    event = create_test_event()
    await backend.write_event(event)
    
    # Query events (placeholder returns empty list)
    queried = await backend.query_events()
    assert isinstance(queried, list)
    
    # Close (should not raise)
    await backend.close()


def test_event_type_enum():
    """Test EventType enum values."""
    assert EventType.USER_LOGIN.value == "user_login"
    assert EventType.RCA_STARTED.value == "rca_started"
    assert EventType.API_CALL.value == "api_call"


@pytest.mark.asyncio
async def test_file_backend_close():
    """Test file backend close doesn't raise."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        await backend.initialize()
        
        # Should not raise
        await backend.close()


@pytest.mark.asyncio
async def test_audit_system_close():
    """Test audit system close."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "audit.jsonl"
        backend = FileAuditBackend(str(file_path))
        system = AuditSystem(backend)
        
        await system.initialize()
        await system.close()

