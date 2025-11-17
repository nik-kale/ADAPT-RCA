"""
Cloud provider integrations for log ingestion.

Supports pulling logs from AWS CloudWatch, GCP Cloud Logging, and Azure Monitor.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CloudLogEntry:
    """Represents a log entry from cloud provider."""
    timestamp: datetime
    message: str
    severity: str
    source: str
    resource: Dict[str, str]
    labels: Dict[str, str]
    raw: Dict[str, Any]


class CloudIntegration(ABC):
    """Base class for cloud provider integrations."""

    @abstractmethod
    def fetch_logs(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Iterator[CloudLogEntry]:
        """
        Fetch logs from cloud provider.

        Args:
            start_time: Start of time range
            end_time: End of time range (defaults to now)
            filters: Optional filters (provider-specific)

        Yields:
            CloudLogEntry objects
        """
        pass


class AWSCloudWatchIntegration(CloudIntegration):
    """
    AWS CloudWatch Logs integration.

    Fetches logs from CloudWatch log groups and streams.

    Example:
        >>> integration = AWSCloudWatchIntegration(
        ...     region="us-west-2",
        ...     log_group="/aws/lambda/my-function"
        ... )
        >>> logs = list(integration.fetch_logs(
        ...     start_time=datetime.now() - timedelta(hours=1)
        ... ))
    """

    def __init__(
        self,
        region: str,
        log_group: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        profile_name: Optional[str] = None
    ):
        """
        Initialize AWS CloudWatch integration.

        Args:
            region: AWS region
            log_group: CloudWatch log group name
            aws_access_key_id: Optional AWS access key
            aws_secret_access_key: Optional AWS secret key
            profile_name: Optional AWS profile name
        """
        self.region = region
        self.log_group = log_group

        try:
            import boto3
            self.boto3 = boto3

            # Create client
            if profile_name:
                session = boto3.Session(profile_name=profile_name)
                self.client = session.client('logs', region_name=region)
            elif aws_access_key_id and aws_secret_access_key:
                self.client = boto3.client(
                    'logs',
                    region_name=region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )
            else:
                # Use default credentials
                self.client = boto3.client('logs', region_name=region)

            logger.info(f"Initialized AWS CloudWatch integration for {log_group}")

        except ImportError:
            raise ImportError(
                "boto3 required for AWS integration. Install with: pip install boto3"
            )

    def fetch_logs(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Iterator[CloudLogEntry]:
        """
        Fetch logs from CloudWatch.

        Args:
            start_time: Start of time range
            end_time: End of time range (defaults to now)
            filters: Optional filters with keys:
                - log_stream_prefix: Filter by log stream name prefix
                - filter_pattern: CloudWatch Logs filter pattern

        Yields:
            CloudLogEntry objects
        """
        if end_time is None:
            end_time = datetime.now()

        filters = filters or {}

        # Convert to milliseconds (CloudWatch requirement)
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        try:
            # Filter logs
            params = {
                'logGroupName': self.log_group,
                'startTime': start_ms,
                'endTime': end_ms
            }

            if 'log_stream_prefix' in filters:
                params['logStreamNamePrefix'] = filters['log_stream_prefix']

            if 'filter_pattern' in filters:
                params['filterPattern'] = filters['filter_pattern']

            # Paginate through results
            paginator = self.client.get_paginator('filter_log_events')
            page_iterator = paginator.paginate(**params)

            for page in page_iterator:
                for event in page.get('events', []):
                    yield CloudLogEntry(
                        timestamp=datetime.fromtimestamp(event['timestamp'] / 1000),
                        message=event['message'],
                        severity=self._extract_severity(event['message']),
                        source=event.get('logStreamName', 'unknown'),
                        resource={
                            'type': 'cloudwatch_log_stream',
                            'log_group': self.log_group,
                            'log_stream': event.get('logStreamName', ''),
                            'region': self.region
                        },
                        labels={
                            'provider': 'aws',
                            'service': 'cloudwatch'
                        },
                        raw=event
                    )

        except Exception as e:
            logger.error(f"Error fetching CloudWatch logs: {e}")
            raise

    def _extract_severity(self, message: str) -> str:
        """Extract severity from log message."""
        message_upper = message.upper()
        if 'FATAL' in message_upper or 'CRITICAL' in message_upper:
            return 'CRITICAL'
        elif 'ERROR' in message_upper:
            return 'ERROR'
        elif 'WARN' in message_upper:
            return 'WARNING'
        elif 'INFO' in message_upper:
            return 'INFO'
        elif 'DEBUG' in message_upper:
            return 'DEBUG'
        else:
            return 'INFO'


class GCPLoggingIntegration(CloudIntegration):
    """
    Google Cloud Platform Cloud Logging integration.

    Fetches logs from GCP Cloud Logging.

    Example:
        >>> integration = GCPLoggingIntegration(
        ...     project_id="my-project",
        ...     credentials_path="/path/to/service-account.json"
        ... )
        >>> logs = list(integration.fetch_logs(
        ...     start_time=datetime.now() - timedelta(hours=1),
        ...     filters={'resource_type': 'gce_instance'}
        ... ))
    """

    def __init__(
        self,
        project_id: str,
        credentials_path: Optional[str] = None
    ):
        """
        Initialize GCP Cloud Logging integration.

        Args:
            project_id: GCP project ID
            credentials_path: Optional path to service account JSON
        """
        self.project_id = project_id

        try:
            from google.cloud import logging as gcp_logging
            from google.oauth2 import service_account

            if credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path
                )
                self.client = gcp_logging.Client(
                    project=project_id,
                    credentials=credentials
                )
            else:
                # Use default credentials
                self.client = gcp_logging.Client(project=project_id)

            logger.info(f"Initialized GCP Cloud Logging for project: {project_id}")

        except ImportError:
            raise ImportError(
                "google-cloud-logging required. Install with: pip install google-cloud-logging"
            )

    def fetch_logs(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Iterator[CloudLogEntry]:
        """
        Fetch logs from GCP Cloud Logging.

        Args:
            start_time: Start of time range
            end_time: End of time range
            filters: Optional filters with keys:
                - resource_type: GCP resource type
                - log_name: Log name
                - severity: Minimum severity

        Yields:
            CloudLogEntry objects
        """
        if end_time is None:
            end_time = datetime.now()

        filters = filters or {}

        # Build filter string
        filter_parts = [
            f'timestamp>="{start_time.isoformat()}"',
            f'timestamp<="{end_time.isoformat()}"'
        ]

        if 'resource_type' in filters:
            filter_parts.append(f'resource.type="{filters["resource_type"]}"')

        if 'log_name' in filters:
            filter_parts.append(f'logName="{filters["log_name"]}"')

        if 'severity' in filters:
            filter_parts.append(f'severity>={filters["severity"]}')

        filter_str = ' AND '.join(filter_parts)

        try:
            # List log entries
            entries = self.client.list_entries(filter_=filter_str)

            for entry in entries:
                yield CloudLogEntry(
                    timestamp=entry.timestamp,
                    message=entry.payload if isinstance(entry.payload, str) else str(entry.payload),
                    severity=entry.severity or 'INFO',
                    source=entry.log_name or 'unknown',
                    resource={
                        'type': entry.resource.type if entry.resource else 'unknown',
                        'labels': dict(entry.resource.labels) if entry.resource else {}
                    },
                    labels=dict(entry.labels) if entry.labels else {},
                    raw={
                        'log_name': entry.log_name,
                        'insert_id': entry.insert_id,
                        'trace': entry.trace,
                        'span_id': entry.span_id
                    }
                )

        except Exception as e:
            logger.error(f"Error fetching GCP logs: {e}")
            raise


class AzureMonitorIntegration(CloudIntegration):
    """
    Azure Monitor Logs integration.

    Fetches logs from Azure Monitor using the Log Analytics API.

    Example:
        >>> integration = AzureMonitorIntegration(
        ...     workspace_id="<workspace-id>",
        ...     client_id="<client-id>",
        ...     client_secret="<client-secret>",
        ...     tenant_id="<tenant-id>"
        ... )
        >>> logs = list(integration.fetch_logs(
        ...     start_time=datetime.now() - timedelta(hours=1)
        ... ))
    """

    def __init__(
        self,
        workspace_id: str,
        client_id: str,
        client_secret: str,
        tenant_id: str
    ):
        """
        Initialize Azure Monitor integration.

        Args:
            workspace_id: Log Analytics workspace ID
            client_id: Azure AD application client ID
            client_secret: Azure AD application client secret
            tenant_id: Azure AD tenant ID
        """
        self.workspace_id = workspace_id

        try:
            from azure.identity import ClientSecretCredential
            from azure.monitor.query import LogsQueryClient

            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )

            self.client = LogsQueryClient(credential)

            logger.info(f"Initialized Azure Monitor for workspace: {workspace_id}")

        except ImportError:
            raise ImportError(
                "Azure SDK required. Install with: pip install azure-monitor-query azure-identity"
            )

    def fetch_logs(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Iterator[CloudLogEntry]:
        """
        Fetch logs from Azure Monitor.

        Args:
            start_time: Start of time range
            end_time: End of time range
            filters: Optional filters with keys:
                - query: KQL query (defaults to fetching all)
                - table: Table name (e.g., 'AppTraces', 'AppExceptions')

        Yields:
            CloudLogEntry objects
        """
        if end_time is None:
            end_time = datetime.now()

        filters = filters or {}

        # Build KQL query
        table = filters.get('table', 'AppTraces')
        custom_query = filters.get('query')

        if custom_query:
            query = custom_query
        else:
            query = f"""
                {table}
                | where TimeGenerated between (datetime({start_time.isoformat()}) .. datetime({end_time.isoformat()}))
                | order by TimeGenerated asc
            """

        try:
            from azure.monitor.query import LogsQueryStatus
            from azure.core.exceptions import HttpResponseError

            # Execute query
            response = self.client.query_workspace(
                workspace_id=self.workspace_id,
                query=query,
                timespan=(start_time, end_time)
            )

            if response.status == LogsQueryStatus.SUCCESS:
                for table in response.tables:
                    for row in table.rows:
                        # Convert row to dict
                        row_dict = dict(zip([col.name for col in table.columns], row))

                        yield CloudLogEntry(
                            timestamp=row_dict.get('TimeGenerated', datetime.now()),
                            message=row_dict.get('Message', '') or str(row_dict),
                            severity=row_dict.get('SeverityLevel', 'INFO'),
                            source=row_dict.get('AppRoleName', 'unknown'),
                            resource={
                                'type': 'azure_resource',
                                'table': table.name
                            },
                            labels={
                                'provider': 'azure',
                                'service': 'monitor'
                            },
                            raw=row_dict
                        )

        except Exception as e:
            logger.error(f"Error fetching Azure Monitor logs: {e}")
            raise
