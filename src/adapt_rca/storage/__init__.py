"""
Storage and persistence for ADAPT-RCA.

Provides database persistence for incidents, alerts, and historical data.
"""

from .incident_store import IncidentStore, StoredIncident

__all__ = ["IncidentStore", "StoredIncident"]
