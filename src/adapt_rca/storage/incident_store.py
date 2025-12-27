"""
SQLite-based incident storage for ADAPT-RCA.

Provides persistent storage of incidents, alerts, and analysis results
for historical tracking and trend analysis.
"""
import logging
import sqlite3
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class StoredIncident:
    """Represents a stored incident record."""
    incident_id: str
    created_at: datetime
    resolved_at: Optional[datetime]
    severity: str
    status: str
    affected_services: List[str]
    event_count: int
    root_causes: List[Dict[str, Any]]
    recommended_actions: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    analysis_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['resolved_at'] = self.resolved_at.isoformat() if self.resolved_at else None
        return data


class IncidentStore:
    """
    SQLite-based storage for incidents and alerts.

    Provides CRUD operations and querying capabilities for incident history.
    Supports trend analysis and reporting.

    Example:
        >>> store = IncidentStore("adapt_rca.db")
        >>> store.store_incident(incident_data)
        >>> recent = store.get_recent_incidents(hours=24)
        >>> stats = store.get_incident_stats(days=7)
    """

    def __init__(self, db_path: str | Path = "adapt_rca.db"):
        """
        Initialize incident store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Incidents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    metadata TEXT,
                    analysis_result TEXT,
                    created_timestamp INTEGER NOT NULL
                )
            """)

            # Services table (many-to-many with incidents)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incident_services (
                    incident_id TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id),
                    PRIMARY KEY (incident_id, service_name)
                )
            """)

            # Root causes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS root_causes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    evidence TEXT,
                    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
                )
            """)

            # Recommended actions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommended_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    category TEXT,
                    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
                )
            """)

            # Metrics table for time-series data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    tags TEXT,
                    metadata TEXT
                )
            """)

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_incidents_created
                ON incidents(created_at DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_incidents_severity
                ON incidents(severity)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_incidents_status
                ON incidents(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_name_time
                ON metrics(metric_name, timestamp DESC)
            """)

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def store_incident(
        self,
        incident_id: str,
        created_at: datetime,
        severity: str,
        status: str,
        affected_services: List[str],
        event_count: int,
        root_causes: List[Dict[str, Any]],
        recommended_actions: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        analysis_result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store an incident in the database.

        Args:
            incident_id: Unique incident identifier
            created_at: When incident occurred
            severity: Severity level
            status: Current status
            affected_services: List of affected service names
            event_count: Number of events in incident
            root_causes: List of root cause dictionaries
            recommended_actions: List of recommended action dictionaries
            metadata: Optional additional metadata
            analysis_result: Optional full analysis result

        Returns:
            True if stored successfully
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Insert main incident record
                cursor.execute("""
                    INSERT OR REPLACE INTO incidents (
                        incident_id, created_at, severity, status, event_count,
                        metadata, analysis_result, created_timestamp, resolved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    incident_id,
                    created_at,
                    severity,
                    status,
                    event_count,
                    json.dumps(metadata or {}),
                    json.dumps(analysis_result) if analysis_result else None,
                    int(created_at.timestamp()),
                    None  # resolved_at initially null
                ))

                # Insert affected services
                for service in affected_services:
                    cursor.execute("""
                        INSERT OR IGNORE INTO incident_services (incident_id, service_name)
                        VALUES (?, ?)
                    """, (incident_id, service))

                # Insert root causes
                for rc in root_causes:
                    cursor.execute("""
                        INSERT INTO root_causes (incident_id, description, confidence, evidence)
                        VALUES (?, ?, ?, ?)
                    """, (
                        incident_id,
                        rc.get('description', ''),
                        rc.get('confidence', 0.0),
                        json.dumps(rc.get('evidence', []))
                    ))

                # Insert recommended actions
                for action in recommended_actions:
                    cursor.execute("""
                        INSERT INTO recommended_actions (
                            incident_id, description, priority, category
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        incident_id,
                        action.get('description', ''),
                        action.get('priority', 5),
                        action.get('category', 'unknown')
                    ))

                conn.commit()
                logger.debug(f"Stored incident {incident_id}")
                return True

        except Exception as e:
            logger.error(f"Error storing incident: {e}")
            return False

    def get_incident(self, incident_id: str) -> Optional[StoredIncident]:
        """
        Retrieve a specific incident.

        Args:
            incident_id: Incident ID to retrieve

        Returns:
            StoredIncident or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get main incident
                cursor.execute("""
                    SELECT * FROM incidents WHERE incident_id = ?
                """, (incident_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Get services
                cursor.execute("""
                    SELECT service_name FROM incident_services WHERE incident_id = ?
                """, (incident_id,))
                services = [r['service_name'] for r in cursor.fetchall()]

                # Get root causes
                cursor.execute("""
                    SELECT description, confidence, evidence FROM root_causes
                    WHERE incident_id = ?
                """, (incident_id,))
                root_causes = [
                    {
                        'description': r['description'],
                        'confidence': r['confidence'],
                        'evidence': json.loads(r['evidence'])
                    }
                    for r in cursor.fetchall()
                ]

                # Get actions
                cursor.execute("""
                    SELECT description, priority, category FROM recommended_actions
                    WHERE incident_id = ?
                """, (incident_id,))
                actions = [
                    {
                        'description': r['description'],
                        'priority': r['priority'],
                        'category': r['category']
                    }
                    for r in cursor.fetchall()
                ]

                return StoredIncident(
                    incident_id=row['incident_id'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    resolved_at=datetime.fromisoformat(row['resolved_at']) if row['resolved_at'] else None,
                    severity=row['severity'],
                    status=row['status'],
                    affected_services=services,
                    event_count=row['event_count'],
                    root_causes=root_causes,
                    recommended_actions=actions,
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    analysis_result=json.loads(row['analysis_result']) if row['analysis_result'] else None
                )

        except Exception as e:
            logger.error(f"Error retrieving incident: {e}")
            return None

    def get_recent_incidents(
        self,
        hours: int = 24,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[StoredIncident]:
        """
        Get recent incidents.

        Args:
            hours: How many hours back to look
            severity: Optional severity filter
            status: Optional status filter
            limit: Maximum number of incidents to return

        Returns:
            List of StoredIncident objects
        """
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            cutoff_ts = int(cutoff.timestamp())

            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT incident_id FROM incidents
                    WHERE created_timestamp >= ?
                """
                params = [cutoff_ts]

                if severity:
                    query += " AND severity = ?"
                    params.append(severity)

                if status:
                    query += " AND status = ?"
                    params.append(status)

                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                incident_ids = [r['incident_id'] for r in cursor.fetchall()]

                # Fetch full incident data
                incidents = []
                for incident_id in incident_ids:
                    incident = self.get_incident(incident_id)
                    if incident:
                        incidents.append(incident)

                return incidents

        except Exception as e:
            logger.error(f"Error retrieving recent incidents: {e}")
            return []

    def get_incident_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get incident statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with incident statistics
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = int(cutoff.timestamp())

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Total incidents
                cursor.execute("""
                    SELECT COUNT(*) as count FROM incidents
                    WHERE created_timestamp >= ?
                """, (cutoff_ts,))
                total = cursor.fetchone()['count']

                # By severity
                cursor.execute("""
                    SELECT severity, COUNT(*) as count FROM incidents
                    WHERE created_timestamp >= ?
                    GROUP BY severity
                """, (cutoff_ts,))
                by_severity = {r['severity']: r['count'] for r in cursor.fetchall()}

                # By status
                cursor.execute("""
                    SELECT status, COUNT(*) as count FROM incidents
                    WHERE created_timestamp >= ?
                    GROUP BY status
                """, (cutoff_ts,))
                by_status = {r['status']: r['count'] for r in cursor.fetchall()}

                # Top affected services
                cursor.execute("""
                    SELECT service_name, COUNT(*) as count
                    FROM incident_services s
                    JOIN incidents i ON s.incident_id = i.incident_id
                    WHERE i.created_timestamp >= ?
                    GROUP BY service_name
                    ORDER BY count DESC
                    LIMIT 10
                """, (cutoff_ts,))
                top_services = [
                    {'service': r['service_name'], 'count': r['count']}
                    for r in cursor.fetchall()
                ]

                return {
                    'total_incidents': total,
                    'by_severity': by_severity,
                    'by_status': by_status,
                    'top_services': top_services,
                    'time_period_days': days
                }

        except Exception as e:
            logger.error(f"Error getting incident stats: {e}")
            return {}

    def store_metric(
        self,
        metric_name: str,
        metric_value: float,
        timestamp: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store a metric value.

        Args:
            metric_name: Name of the metric
            metric_value: Metric value
            timestamp: Optional timestamp (defaults to now)
            tags: Optional tags
            metadata: Optional metadata

        Returns:
            True if stored successfully
        """
        try:
            if timestamp is None:
                timestamp = datetime.now()

            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO metrics (metric_name, metric_value, timestamp, tags, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    metric_name,
                    metric_value,
                    timestamp,
                    json.dumps(tags or {}),
                    json.dumps(metadata or {})
                ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error storing metric: {e}")
            return False

    def get_metrics(
        self,
        metric_name: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get metric values.

        Args:
            metric_name: Metric name
            hours: How many hours back

        Returns:
            List of metric dictionaries
        """
        try:
            cutoff = datetime.now() - timedelta(hours=hours)

            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM metrics
                    WHERE metric_name = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (metric_name, cutoff))

                return [
                    {
                        'metric_name': r['metric_name'],
                        'metric_value': r['metric_value'],
                        'timestamp': r['timestamp'],
                        'tags': json.loads(r['tags']) if r['tags'] else {},
                        'metadata': json.loads(r['metadata']) if r['metadata'] else {}
                    }
                    for r in cursor.fetchall()
                ]

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return []

    def cleanup_old_data(self, days: int = 90) -> int:
        """
        Remove data older than specified days.

        Args:
            days: Age threshold for cleanup

        Returns:
            Number of incidents removed
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = int(cutoff.timestamp())

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get incident IDs to delete
                cursor.execute("""
                    SELECT incident_id FROM incidents
                    WHERE created_timestamp < ?
                """, (cutoff_ts,))
                incident_ids = [r['incident_id'] for r in cursor.fetchall()]

                if not incident_ids:
                    return 0

                # Delete related data
                placeholders = ','.join('?' * len(incident_ids))

                cursor.execute(f"""
                    DELETE FROM incident_services WHERE incident_id IN ({placeholders})
                """, incident_ids)

                cursor.execute(f"""
                    DELETE FROM root_causes WHERE incident_id IN ({placeholders})
                """, incident_ids)

                cursor.execute(f"""
                    DELETE FROM recommended_actions WHERE incident_id IN ({placeholders})
                """, incident_ids)

                cursor.execute(f"""
                    DELETE FROM incidents WHERE incident_id IN ({placeholders})
                """, incident_ids)

                # Cleanup old metrics
                cursor.execute("""
                    DELETE FROM metrics WHERE timestamp < ?
                """, (cutoff,))

                conn.commit()
                count = len(incident_ids)
                logger.info(f"Cleaned up {count} old incidents")
                return count

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return 0
