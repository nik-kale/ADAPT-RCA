#!/usr/bin/env python3
"""
Example: Using LLM-powered analysis with ADAPT-RCA

This script demonstrates how to:
1. Configure LLM providers (OpenAI or Anthropic)
2. Perform AI-powered root cause analysis
3. Compare LLM vs heuristic analysis
"""
import os
from pathlib import Path
from adapt_rca.ingestion import load_jsonl
from adapt_rca.models import Event, IncidentGroup
from adapt_rca.reasoning import analyze_incident_group
from adapt_rca.reasoning.llm_agent import analyze_with_llm
from adapt_rca.llm.factory import get_llm_provider
from adapt_rca.graph.causal_graph import CausalGraph
from adapt_rca.config import RCAConfig


def main():
    # Check for API keys
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: No LLM API key found!")
        print("Please set either:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        return

    # Configure LLM provider
    provider_name = "openai" if os.getenv("OPENAI_API_KEY") else "anthropic"
    model = "gpt-4" if provider_name == "openai" else "claude-3-sonnet-20240229"

    print(f"Using {provider_name} with model {model}")

    # Load configuration
    config = RCAConfig()
    config.validate()

    # Get LLM provider
    llm_provider = get_llm_provider(
        provider_name=provider_name,
        model=model,
        timeout=config.llm_timeout
    )

    # Load multi-service incident
    data_file = Path(__file__).parent.parent / "data" / "sample_multi_service.jsonl"
    print(f"\nLoading incident from {data_file}...")

    events = []
    for event_dict in load_jsonl(data_file):
        events.append(Event(**event_dict))

    incident = IncidentGroup.from_events(events)
    print(f"Loaded {len(events)} events affecting {len(incident.services)} services")

    # Build causal graph
    print("\nBuilding causal graph...")
    graph = CausalGraph.from_incident_group(incident)
    graph_dict = graph.to_dict()

    # Perform LLM analysis
    print(f"\nPerforming LLM-powered analysis with {provider_name}...")
    llm_result = analyze_with_llm(incident, llm_provider, graph_dict)

    # Also run heuristic analysis for comparison
    print("Performing heuristic analysis for comparison...")
    heuristic_result = analyze_incident_group(incident)

    # Display results
    print("\n" + "=" * 70)
    print("LLM-POWERED ANALYSIS")
    print("=" * 70)
    print(f"\n{llm_result.incident_summary}\n")

    print("Root Causes (LLM):")
    for i, cause in enumerate(llm_result.probable_root_causes, 1):
        print(f"  {i}. {cause.description} (confidence: {cause.confidence:.1%})")

    print("\nRecommended Actions (LLM):")
    for i, action in enumerate(llm_result.recommended_actions[:5], 1):
        print(f"  {i}. [P{action.priority}] {action.description}")

    print("\n" + "=" * 70)
    print("HEURISTIC ANALYSIS (for comparison)")
    print("=" * 70)
    print(f"\n{heuristic_result.incident_summary}\n")

    print("Root Causes (Heuristic):")
    for i, cause in enumerate(heuristic_result.probable_root_causes, 1):
        print(f"  {i}. {cause.description} (confidence: {cause.confidence:.1%})")

    print("\n✓ Analysis complete!")
    print(f"\nLLM usage: {llm_result.metadata.get('llm_analysis', False)}")


if __name__ == "__main__":
    main()
