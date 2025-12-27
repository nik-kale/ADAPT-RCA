#!/usr/bin/env python3
"""
Example: Visualizing causal graphs with ADAPT-RCA

This script demonstrates how to:
1. Build causal graphs from incidents
2. Export to Mermaid and DOT formats
3. Identify root causes from graph topology
"""
from pathlib import Path
from adapt_rca.ingestion import load_jsonl
from adapt_rca.models import Event, IncidentGroup
from adapt_rca.graph.causal_graph import CausalGraph
from adapt_rca.reporting import export_graph_mermaid, export_graph_dot


def main():
    # Load incident
    data_file = Path(__file__).parent.parent / "data" / "sample_multi_service.jsonl"
    print(f"Loading incident from {data_file}...")

    events = []
    for event_dict in load_jsonl(data_file):
        events.append(Event(**event_dict))

    incident = IncidentGroup.from_events(events)
    print(f"Loaded {len(events)} events from {len(incident.services)} services")

    # Build causal graph
    print("\nBuilding causal graph with temporal analysis...")
    graph = CausalGraph.from_incident_group(incident)

    print(f"  Nodes (services): {len(graph.nodes)}")
    print(f"  Edges (causal relationships): {len(graph.edges)}")

    # Identify root causes
    root_causes = graph.get_root_causes()
    print(f"\nIdentified root cause services: {', '.join(root_causes) if root_causes else 'None'}")

    # Display graph details
    print("\nService Error Counts:")
    for service_id, node in sorted(graph.nodes.items(), key=lambda x: x[1].error_count, reverse=True):
        print(f"  {service_id}: {node.error_count} error(s)")
        if node.first_error:
            print(f"    First error: {node.first_error.isoformat()}")

    print("\nCausal Relationships (temporal dependencies):")
    for edge in sorted(graph.edges, key=lambda e: e.confidence, reverse=True)[:10]:
        time_info = ""
        if edge.time_delta:
            time_info = f" ({edge.time_delta.total_seconds():.0f}s apart)"
        print(f"  {edge.from_node} → {edge.to_node}")
        print(f"    Confidence: {edge.confidence:.2f}{time_info}")

    # Export visualizations
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"\nExporting graph visualizations to {output_dir}...")

    # Export as Mermaid diagram
    mermaid_file = output_dir / "causal_graph.mmd"
    export_graph_mermaid(graph.to_dict(), mermaid_file)
    print(f"  ✓ Mermaid: {mermaid_file}")
    print("    You can visualize this at https://mermaid.live")

    # Export as DOT format (Graphviz)
    dot_file = output_dir / "causal_graph.dot"
    export_graph_dot(graph.to_dict(), dot_file)
    print(f"  ✓ DOT: {dot_file}")
    print("    Generate image: dot -Tpng causal_graph.dot -o graph.png")

    # Display Mermaid content
    print("\nMermaid diagram preview:")
    print("-" * 70)
    with open(mermaid_file) as f:
        print(f.read())
    print("-" * 70)

    print("\n✓ Visualization complete!")


if __name__ == "__main__":
    main()
