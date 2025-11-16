"""
Enhanced CLI with full feature support.
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import RCAConfig
from .ingestion.file_loader import load_jsonl
from .ingestion.csv_loader import load_csv
from .ingestion.text_loader import load_text_log
from .parsing.log_parser import normalize_event
from .reasoning.heuristics import simple_grouping, time_window_grouping
from .reasoning.agent import analyze_incident, analyze_incident_group
from .reporting.formatter import format_human_readable
from .reporting.exporters import export_json, export_markdown, export_graph_mermaid, export_graph_dot
from .utils import validate_input_path, validate_output_path, PathValidationError
from .models import Event, IncidentGroup
from .graph.causal_graph import CausalGraph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure logging level based on verbosity flags."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    elif verbose:
        logging.getLogger().setLevel(logging.INFO)
        logger.info("Verbose logging enabled")
    else:
        logging.getLogger().setLevel(logging.WARNING)


def load_events_from_file(
    input_path: Path,
    file_format: str = "auto"
) -> List[Dict[str, Any]]:
    """
    Load events from file based on format.

    Args:
        input_path: Path to input file
        file_format: Format (auto, jsonl, csv, syslog, text, nginx, apache)

    Returns:
        List of raw event dictionaries

    Raises:
        ValueError: If format is unknown or loading fails
    """
    suffix = input_path.suffix.lower()

    # Auto-detect format
    if file_format == "auto":
        if suffix == ".jsonl":
            file_format = "jsonl"
        elif suffix == ".csv":
            file_format = "csv"
        elif suffix in [".log", ".txt"]:
            file_format = "syslog"  # Try syslog first
        else:
            file_format = "jsonl"  # Default

    logger.info(f"Loading file as format: {file_format}")

    # Load based on format
    if file_format == "jsonl":
        return list(load_jsonl(input_path))
    elif file_format == "csv":
        return list(load_csv(input_path))
    elif file_format in ["syslog", "text", "nginx", "apache", "generic"]:
        return list(load_text_log(input_path, log_format=file_format))
    else:
        raise ValueError(f"Unknown format: {file_format}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ADAPT-RCA: Advanced Root Cause Analysis for logs and events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  %(prog)s --input logs.jsonl

  # With LLM analysis (requires API key)
  %(prog)s --input logs.jsonl --use-llm

  # CSV logs with graph export
  %(prog)s --input logs.csv --format csv --export-graph graph.mmd

  # Syslog with all outputs
  %(prog)s --input system.log --format syslog --output report.json --export-markdown report.md

  # Web logs with time window grouping
  %(prog)s --input access.log --format nginx --use-time-window

Environment Variables:
  ADAPT_RCA_LLM_PROVIDER   LLM provider (openai, anthropic, none)
  ADAPT_RCA_LLM_MODEL      Model to use (gpt-4, claude-3-opus, etc.)
  ADAPT_RCA_MAX_EVENTS     Maximum events to process (default: 5000)
  ADAPT_RCA_TIME_WINDOW    Time window in minutes (default: 15)
  OPENAI_API_KEY           OpenAI API key (if using openai provider)
  ANTHROPIC_API_KEY        Anthropic API key (if using anthropic provider)
        """
    )

    # Input/Output
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to log file"
    )
    parser.add_argument(
        "--output", "-o",
        help="Path to write JSON results"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["auto", "jsonl", "csv", "syslog", "text", "nginx", "apache", "generic"],
        default="auto",
        help="Input file format (default: auto-detect)"
    )

    # Analysis options
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM for analysis (requires LLM provider configured)"
    )
    parser.add_argument(
        "--use-time-window",
        action="store_true",
        help="Use time-window based event grouping (default: simple grouping)"
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic", "none"],
        help="Override LLM provider (overrides ADAPT_RCA_LLM_PROVIDER)"
    )
    parser.add_argument(
        "--llm-model",
        help="Override LLM model (overrides ADAPT_RCA_LLM_MODEL)"
    )

    # Export options
    parser.add_argument(
        "--export-markdown",
        metavar="PATH",
        help="Export results as Markdown"
    )
    parser.add_argument(
        "--export-graph",
        metavar="PATH",
        help="Export causal graph (format based on extension: .mmd or .dot)"
    )

    # Logging options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, debug=args.debug)

    try:
        # Validate and load configuration
        config = RCAConfig()

        # Override LLM settings if provided
        if args.llm_provider:
            config.llm_provider = args.llm_provider
        if args.llm_model:
            config.llm_model = args.llm_model

        config.validate()
        logger.debug(f"Configuration: {config}")

        # Validate input path
        try:
            input_path = validate_input_path(args.input)
            logger.info(f"Loading events from: {input_path}")
        except PathValidationError as e:
            logger.error(f"Input validation failed: {e}")
            sys.exit(1)

        # Load events
        try:
            raw_events = load_events_from_file(input_path, args.format)
            logger.info(f"Loaded {len(raw_events)} raw events")

            if not raw_events:
                logger.warning("No events found in input file")
                print("No events to analyze.")
                sys.exit(0)

            # Apply max_events limit
            if len(raw_events) > config.max_events:
                logger.warning(
                    f"Limiting analysis to {config.max_events} events "
                    f"(found {len(raw_events)})"
                )
                raw_events = raw_events[:config.max_events]

            # Normalize to Event objects
            event_objects = [Event(**normalize_event(e)) for e in raw_events]
            logger.info(f"Normalized {len(event_objects)} events")

        except Exception as e:
            logger.error(f"Failed to load events: {e}", exc_info=args.debug)
            sys.exit(1)

        # Group events into incidents
        try:
            if args.use_time_window:
                logger.info(f"Using time-window grouping ({config.time_window_minutes} min)")
                incident_groups = time_window_grouping(
                    event_objects,
                    window_minutes=config.time_window_minutes
                )
            else:
                # Convert Event objects to dicts for simple_grouping
                event_dicts = [e.model_dump() for e in event_objects]
                groups_dicts = simple_grouping(event_dicts)

                # Convert back to IncidentGroup objects
                incident_groups = [
                    IncidentGroup.from_events([Event(**e) for e in g])
                    for g in groups_dicts
                ]

            logger.info(f"Grouped events into {len(incident_groups)} incident(s)")

            if not incident_groups:
                logger.warning("No incident groups identified")
                print("No incidents identified.")
                sys.exit(0)

        except Exception as e:
            logger.error(f"Failed to group events: {e}", exc_info=args.debug)
            sys.exit(1)

        # Analyze the first incident group
        try:
            incident = incident_groups[0] if incident_groups else IncidentGroup()

            # Check if LLM should be used
            use_llm = args.use_llm and config.llm_provider != "none"

            if use_llm:
                logger.info(f"Using LLM analysis ({config.llm_provider}/{config.llm_model})")
                try:
                    from .llm.factory import get_llm_provider
                    from .reasoning.llm_agent import analyze_with_llm

                    llm_provider = get_llm_provider(
                        config.llm_provider,
                        model=config.llm_model
                    )

                    if llm_provider:
                        # Build causal graph first
                        causal_graph = CausalGraph.from_incident_group(incident)
                        analysis_result = analyze_with_llm(
                            incident,
                            llm_provider,
                            causal_graph.to_dict()
                        )
                    else:
                        logger.warning("LLM provider is None, falling back to heuristic analysis")
                        analysis_result = analyze_incident_group(incident)

                except ImportError as e:
                    logger.error(f"LLM dependencies not installed: {e}")
                    logger.info("Falling back to heuristic analysis")
                    analysis_result = analyze_incident_group(incident)
            else:
                logger.info("Using heuristic analysis")
                analysis_result = analyze_incident_group(incident)

            logger.info("Analysis complete")

            # Convert to legacy format for display
            result_dict = analysis_result.to_legacy_dict()

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=args.debug)
            sys.exit(1)

        # Display results
        print(format_human_readable(result_dict))

        # Save JSON output if requested
        if args.output:
            try:
                # Use full analysis result (not legacy format)
                full_result = analysis_result.model_dump(mode='json')
                export_json(full_result, args.output)
                print(f"\n✓ Results saved to: {args.output}")

            except Exception as e:
                logger.error(f"Failed to write output: {e}", exc_info=args.debug)
                sys.exit(1)

        # Export markdown if requested
        if args.export_markdown:
            try:
                full_result = analysis_result.model_dump(mode='json')
                export_markdown(full_result, args.export_markdown)
                print(f"✓ Markdown report saved to: {args.export_markdown}")

            except Exception as e:
                logger.error(f"Failed to export markdown: {e}", exc_info=args.debug)
                sys.exit(1)

        # Export graph if requested
        if args.export_graph:
            try:
                if not analysis_result.causal_graph:
                    logger.warning("No causal graph available to export")
                else:
                    graph_path = Path(args.export_graph)
                    ext = graph_path.suffix.lower()

                    if ext in ['.mmd', '.mermaid']:
                        export_graph_mermaid(analysis_result.causal_graph, graph_path)
                        print(f"✓ Mermaid graph saved to: {args.export_graph}")
                    elif ext in ['.dot', '.gv']:
                        export_graph_dot(analysis_result.causal_graph, graph_path)
                        print(f"✓ DOT graph saved to: {args.export_graph}")
                    else:
                        logger.error(f"Unknown graph format: {ext} (use .mmd or .dot)")
                        sys.exit(1)

            except Exception as e:
                logger.error(f"Failed to export graph: {e}", exc_info=args.debug)
                sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=args.debug)
        sys.exit(1)


if __name__ == "__main__":
    main()
