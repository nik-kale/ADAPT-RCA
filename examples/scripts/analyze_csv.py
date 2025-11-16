#!/usr/bin/env python3
"""
Example: Analyzing CSV log files with ADAPT-RCA

This script demonstrates how to:
1. Load events from a CSV file
2. Perform root cause analysis
3. Export results in multiple formats
"""
from pathlib import Path
from adapt_rca.ingestion import load_csv
from adapt_rca.models import Event
from adapt_rca.reasoning import analyze_incident_group
from adapt_rca.reporting import export_json, export_markdown, export_graph_mermaid


def main():
    # Path to CSV file
    csv_file = Path(__file__).parent.parent / "data" / "sample_csv.csv"

    print(f"Loading events from {csv_file}...")

    # Load events from CSV
    events = []
    for event_dict in load_csv(csv_file):
        # Convert dict to Event object
        event = Event(**event_dict)
        events.append(event)

    print(f"Loaded {len(events)} events")

    # Perform analysis
    print("\nAnalyzing incident...")
    result = analyze_incident_group(events)

    # Print summary
    print("\n" + "=" * 70)
    print("INCIDENT ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"\n{result.incident_summary}\n")

    print(f"Events analyzed: {result.event_count}")
    print(f"Affected services: {', '.join(result.affected_services)}")

    print("\n--- Probable Root Causes ---")
    for i, cause in enumerate(result.probable_root_causes, 1):
        print(f"\n{i}. {cause.description}")
        print(f"   Confidence: {cause.confidence:.1%}")
        if cause.evidence:
            print("   Evidence:")
            for evidence in cause.evidence:
                print(f"   - {evidence}")

    print("\n--- Recommended Actions ---")
    for i, action in enumerate(result.recommended_actions, 1):
        print(f"{i}. [P{action.priority}] {action.description}")
        print(f"   Category: {action.category}")

    # Export results
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"\nExporting results to {output_dir}...")

    # Export as JSON
    json_file = output_dir / "analysis_result.json"
    export_json(result, json_file)
    print(f"  ✓ JSON: {json_file}")

    # Export as Markdown
    md_file = output_dir / "analysis_report.md"
    export_markdown(result, md_file)
    print(f"  ✓ Markdown: {md_file}")

    # Export causal graph
    if result.causal_graph:
        graph_file = output_dir / "causal_graph.mmd"
        export_graph_mermaid(result.causal_graph, graph_file)
        print(f"  ✓ Mermaid diagram: {graph_file}")

    print("\n✓ Analysis complete!")


if __name__ == "__main__":
    main()
