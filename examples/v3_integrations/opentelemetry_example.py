#!/usr/bin/env python3
"""
OpenTelemetry Integration Example for ADAPT-RCA

This example demonstrates how to:
1. Load and parse OpenTelemetry traces
2. Analyze distributed traces for performance issues
3. Detect error propagation across microservices
4. Identify critical paths and bottlenecks
5. Map service dependencies

Usage:
    python opentelemetry_example.py
"""

import json
from datetime import datetime
from typing import List, Dict, Any

from adapt_rca.integrations import OpenTelemetryAnalyzer, Trace, Span


def create_sample_trace() -> Trace:
    """Create a sample distributed trace for demonstration."""
    trace = Trace(
        trace_id="abc123def456",
        root_span_id="span-1"
    )

    # API Gateway receives request
    trace.add_span(Span(
        span_id="span-1",
        parent_span_id=None,
        service_name="api-gateway",
        operation_name="POST /api/checkout",
        start_time=1234567890.0,
        end_time=1234567895.5,  # 5.5 seconds total
        status="OK",
        attributes={
            "http.method": "POST",
            "http.url": "/api/checkout",
            "http.status_code": 200
        }
    ))

    # Auth service validates token
    trace.add_span(Span(
        span_id="span-2",
        parent_span_id="span-1",
        service_name="auth-service",
        operation_name="validate_token",
        start_time=1234567890.5,
        end_time=1234567891.0,  # 500ms
        status="OK",
        attributes={"user_id": "user123"}
    ))

    # Inventory service checks stock
    trace.add_span(Span(
        span_id="span-3",
        parent_span_id="span-1",
        service_name="inventory-service",
        operation_name="check_stock",
        start_time=1234567891.0,
        end_time=1234567891.5,  # 500ms
        status="OK",
        attributes={"sku": "PROD-123", "quantity": 1}
    ))

    # Payment service processes payment
    trace.add_span(Span(
        span_id="span-4",
        parent_span_id="span-1",
        service_name="payment-service",
        operation_name="process_payment",
        start_time=1234567891.5,
        end_time=1234567894.5,  # 3 seconds (slow!)
        status="OK",
        attributes={
            "amount": 99.99,
            "currency": "USD",
            "gateway": "stripe"
        }
    ))

    # Payment gateway API call (nested under payment service)
    trace.add_span(Span(
        span_id="span-5",
        parent_span_id="span-4",
        service_name="payment-gateway",
        operation_name="charge",
        start_time=1234567891.6,
        end_time=1234567894.4,  # 2.8 seconds (very slow!)
        status="OK",
        attributes={"gateway": "stripe"}
    ))

    # Order service creates order
    trace.add_span(Span(
        span_id="span-6",
        parent_span_id="span-1",
        service_name="order-service",
        operation_name="create_order",
        start_time=1234567894.5,
        end_time=1234567895.0,  # 500ms
        status="OK",
        attributes={"order_id": "ORD-789"}
    ))

    # Notification service sends email
    trace.add_span(Span(
        span_id="span-7",
        parent_span_id="span-1",
        service_name="notification-service",
        operation_name="send_confirmation",
        start_time=1234567895.0,
        end_time=1234567895.5,  # 500ms
        status="OK",
        attributes={"email": "user@example.com"}
    ))

    return trace


def create_error_trace() -> Trace:
    """Create a trace with errors to demonstrate error propagation."""
    trace = Trace(
        trace_id="error-trace-123",
        root_span_id="span-1"
    )

    # API Gateway receives request
    trace.add_span(Span(
        span_id="span-1",
        parent_span_id=None,
        service_name="api-gateway",
        operation_name="GET /api/user/profile",
        start_time=1234567900.0,
        end_time=1234567903.0,  # 3 seconds
        status="ERROR",
        attributes={
            "http.method": "GET",
            "http.status_code": 500,
            "error": "Internal Server Error"
        }
    ))

    # User service attempts to fetch user
    trace.add_span(Span(
        span_id="span-2",
        parent_span_id="span-1",
        service_name="user-service",
        operation_name="get_user",
        start_time=1234567900.5,
        end_time=1234567902.5,  # 2 seconds
        status="ERROR",
        attributes={
            "user_id": "user456",
            "error": "Database connection timeout"
        }
    ))

    # Database query (root cause)
    trace.add_span(Span(
        span_id="span-3",
        parent_span_id="span-2",
        service_name="postgres-db",
        operation_name="SELECT * FROM users",
        start_time=1234567900.6,
        end_time=1234567902.4,  # 1.8 seconds timeout
        status="ERROR",
        attributes={
            "error": "Connection pool exhausted",
            "pool_size": 10,
            "active_connections": 10
        }
    ))

    return trace


def example_basic_analysis():
    """Basic trace analysis."""
    print("=" * 70)
    print("Example 1: Basic Trace Analysis")
    print("=" * 70)

    trace = create_sample_trace()
    analyzer = OpenTelemetryAnalyzer()

    print(f"\nTrace ID: {trace.trace_id}")
    print(f"Total Spans: {len(trace.spans)}")
    print(f"Duration: {trace.get_duration():.2f}s\n")

    # Analyze trace
    issues = analyzer.analyze_trace(trace)

    print(f"Issues Found: {len(issues)}\n")

    for i, issue in enumerate(issues, 1):
        print(f"Issue {i}:")
        print(f"  Type: {issue['issue']}")
        print(f"  Severity: {issue['severity']}")
        print(f"  Service: {issue['service']}")
        print(f"  Operation: {issue.get('operation', 'N/A')}")
        print(f"  Details: {issue['details']}")
        print()


def example_critical_path():
    """Analyze critical path through trace."""
    print("=" * 70)
    print("Example 2: Critical Path Analysis")
    print("=" * 70)

    trace = create_sample_trace()

    print(f"\nTrace ID: {trace.trace_id}")
    print(f"Total Duration: {trace.get_duration():.2f}s\n")

    # Get critical path (slowest route)
    critical_path = trace.get_critical_path()

    print("Critical Path (slowest execution path):\n")

    total_critical_duration = 0
    for i, span in enumerate(critical_path, 1):
        duration = span.duration
        total_critical_duration += duration
        indent = "  " * (i - 1)
        print(f"{indent}├─ {span.service_name}.{span.operation_name}")
        print(f"{indent}│  Duration: {duration:.3f}s")

    print(f"\nCritical Path Duration: {total_critical_duration:.2f}s")
    print(f"Percentage of Total: {(total_critical_duration / trace.get_duration() * 100):.1f}%")

    # Identify bottleneck
    slowest_span = max(critical_path, key=lambda s: s.duration)
    print(f"\nBottleneck: {slowest_span.service_name}.{slowest_span.operation_name}")
    print(f"  Duration: {slowest_span.duration:.3f}s")
    print(f"  {(slowest_span.duration / trace.get_duration() * 100):.1f}% of total trace time")


def example_error_propagation():
    """Detect error propagation across services."""
    print("=" * 70)
    print("Example 3: Error Propagation Detection")
    print("=" * 70)

    trace = create_error_trace()
    analyzer = OpenTelemetryAnalyzer()

    print(f"\nTrace ID: {trace.trace_id}")
    print(f"Has Errors: {trace.has_errors}\n")

    # Detect error propagation
    propagation = analyzer._detect_error_propagation(trace)

    if propagation:
        print("Error Propagation Detected:\n")
        print(f"Origin Service: {propagation['origin_service']}")
        print(f"Origin Operation: {propagation['origin_operation']}")
        print(f"Error Message: {propagation['error_message']}\n")

        print("Propagation Chain:")
        for i, service in enumerate(propagation['affected_services'], 1):
            print(f"  {i}. {service}")

        print(f"\nTotal Services Affected: {len(propagation['affected_services'])}")
    else:
        print("No error propagation detected")


def example_service_dependencies():
    """Analyze service dependencies from trace."""
    print("=" * 70)
    print("Example 4: Service Dependency Mapping")
    print("=" * 70)

    trace = create_sample_trace()
    analyzer = OpenTelemetryAnalyzer()

    print(f"\nTrace ID: {trace.trace_id}\n")

    # Analyze dependencies
    dependencies = analyzer._analyze_dependencies(trace)

    print("Service Dependencies:\n")

    for dep in dependencies:
        print(f"{dep['caller']} → {dep['callee']}")
        print(f"  Calls: {dep['call_count']}")
        print(f"  Avg Latency: {dep['avg_latency']:.0f}ms")
        print(f"  Total Time: {dep['total_latency']:.3f}s")
        if dep['error_rate'] > 0:
            print(f"  Error Rate: {dep['error_rate']:.1%} ⚠️")
        print()

    # Create dependency graph visualization (text)
    print("Dependency Graph:\n")
    print("  api-gateway")
    print("  ├── auth-service")
    print("  ├── inventory-service")
    print("  ├── payment-service")
    print("  │   └── payment-gateway")
    print("  ├── order-service")
    print("  └── notification-service")


def example_performance_analysis():
    """Detailed performance analysis of trace."""
    print("=" * 70)
    print("Example 5: Performance Analysis")
    print("=" * 70)

    trace = create_sample_trace()

    print(f"\nTrace ID: {trace.trace_id}\n")

    # Analyze performance by service
    service_stats: Dict[str, Dict[str, Any]] = {}

    for span in trace.spans:
        service = span.service_name
        if service not in service_stats:
            service_stats[service] = {
                "count": 0,
                "total_duration": 0,
                "min_duration": float('inf'),
                "max_duration": 0,
                "operations": set()
            }

        stats = service_stats[service]
        stats["count"] += 1
        stats["total_duration"] += span.duration
        stats["min_duration"] = min(stats["min_duration"], span.duration)
        stats["max_duration"] = max(stats["max_duration"], span.duration)
        stats["operations"].add(span.operation_name)

    print("Performance by Service:\n")

    # Sort by total duration (descending)
    sorted_services = sorted(
        service_stats.items(),
        key=lambda x: x[1]["total_duration"],
        reverse=True
    )

    for service, stats in sorted_services:
        avg_duration = stats["total_duration"] / stats["count"]
        print(f"{service}:")
        print(f"  Spans: {stats['count']}")
        print(f"  Total Time: {stats['total_duration']:.3f}s")
        print(f"  Avg Time: {avg_duration:.3f}s")
        print(f"  Min Time: {stats['min_duration']:.3f}s")
        print(f"  Max Time: {stats['max_duration']:.3f}s")
        print(f"  Operations: {', '.join(stats['operations'])}")
        print()

    # Identify slow operations (> 1 second)
    print("Slow Operations (> 1s):\n")
    slow_spans = [span for span in trace.spans if span.duration > 1.0]
    for span in sorted(slow_spans, key=lambda s: s.duration, reverse=True):
        print(f"  {span.service_name}.{span.operation_name}: {span.duration:.3f}s")


def example_from_otlp_json():
    """Load and analyze trace from OTLP JSON format."""
    print("=" * 70)
    print("Example 6: Loading OTLP JSON Format")
    print("=" * 70)

    # Sample OTLP JSON (simplified)
    otlp_json = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": {
                        "service.name": "frontend"
                    }
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "5b8efff798038103d269b633813fc60c",
                                "spanId": "eee19b7ec3c1b174",
                                "parentSpanId": "",
                                "name": "GET /",
                                "startTimeUnixNano": 1234567890000000000,
                                "endTimeUnixNano": 1234567892000000000,
                                "status": {"code": "STATUS_CODE_OK"},
                                "attributes": {
                                    "http.method": "GET",
                                    "http.status_code": 200
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }

    print("\nParsing OTLP JSON format...\n")
    print(f"Resource Spans: {len(otlp_json['resourceSpans'])}")

    # Convert to ADAPT-RCA format
    traces: Dict[str, Trace] = {}

    for resource_span in otlp_json["resourceSpans"]:
        service_name = resource_span["resource"]["attributes"].get("service.name", "unknown")

        for scope_span in resource_span["scopeSpans"]:
            for span_data in scope_span["spans"]:
                trace_id = span_data["traceId"]

                # Create trace if doesn't exist
                if trace_id not in traces:
                    traces[trace_id] = Trace(
                        trace_id=trace_id,
                        root_span_id=span_data["spanId"]
                    )

                # Add span
                span = Span(
                    span_id=span_data["spanId"],
                    parent_span_id=span_data.get("parentSpanId") or None,
                    service_name=service_name,
                    operation_name=span_data["name"],
                    start_time=span_data["startTimeUnixNano"] / 1e9,
                    end_time=span_data["endTimeUnixNano"] / 1e9,
                    status=span_data["status"]["code"],
                    attributes=span_data.get("attributes", {})
                )
                traces[trace_id].add_span(span)

    print(f"✅ Parsed {len(traces)} trace(s)")

    # Analyze each trace
    analyzer = OpenTelemetryAnalyzer()
    for trace in traces.values():
        print(f"\nTrace {trace.trace_id}:")
        print(f"  Spans: {len(trace.spans)}")
        print(f"  Duration: {trace.get_duration():.3f}s")

        issues = analyzer.analyze_trace(trace)
        if issues:
            print(f"  Issues: {len(issues)}")
            for issue in issues:
                print(f"    - {issue['issue']}: {issue['details']}")
        else:
            print("  ✅ No issues detected")


def main():
    """Run all examples."""
    import sys

    print("\n" + "=" * 70)
    print("ADAPT-RCA OpenTelemetry Integration Examples")
    print("=" * 70 + "\n")

    examples = [
        ("Basic Analysis", example_basic_analysis),
        ("Critical Path", example_critical_path),
        ("Error Propagation", example_error_propagation),
        ("Service Dependencies", example_service_dependencies),
        ("Performance Analysis", example_performance_analysis),
        ("OTLP JSON Format", example_from_otlp_json),
    ]

    if len(sys.argv) > 1:
        try:
            example_num = int(sys.argv[1]) - 1
            if 0 <= example_num < len(examples):
                name, func = examples[example_num]
                print(f"Running Example: {name}\n")
                func()
            else:
                print(f"Invalid example number. Choose 1-{len(examples)}")
        except ValueError:
            print("Usage: python opentelemetry_example.py [example_number]")
    else:
        for i, (name, func) in enumerate(examples, 1):
            try:
                func()
                print("\n")
            except KeyboardInterrupt:
                print("\n\nExamples interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Example {i} failed: {e}\n")
                import traceback
                traceback.print_exc()
                continue


if __name__ == "__main__":
    main()
