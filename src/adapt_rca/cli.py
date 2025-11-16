"""
Enhanced CLI with subcommand support for better organization.
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from . import __version__
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


def setup_logging(verbose: bool = False, quiet: bool = False, debug: bool = False) -> None:
    """Configure logging level based on verbosity flags."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    elif quiet:
        logging.getLogger().setLevel(logging.ERROR)
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


def handle_analyze(args: argparse.Namespace) -> int:
    """
    Handle the analyze subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Validate and load configuration
        config = RCAConfig.load(args.config_file) if hasattr(args, 'config_file') and args.config_file else RCAConfig.load()

        # Override LLM settings if provided
        if hasattr(args, 'llm_provider') and args.llm_provider:
            config.llm_provider = args.llm_provider
        if hasattr(args, 'llm_model') and args.llm_model:
            config.llm_model = args.llm_model

        config.validate()
        logger.debug(f"Configuration: {config}")

        # Validate input path
        try:
            input_path = validate_input_path(args.input)
            logger.info(f"Loading events from: {input_path}")
        except PathValidationError as e:
            logger.error(f"Input validation failed: {e}")
            return 1

        # Load events
        try:
            raw_events = load_events_from_file(input_path, args.format)
            logger.info(f"Loaded {len(raw_events)} raw events")

            if not raw_events:
                logger.warning("No events found in input file")
                print("No events to analyze.")
                return 0

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
            logger.error(f"Failed to load events: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
            return 1

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
                return 0

        except Exception as e:
            logger.error(f"Failed to group events: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
            return 1

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
            logger.error(f"Analysis failed: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
            return 1

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
                logger.error(f"Failed to write output: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
                return 1

        # Export markdown if requested
        if args.export_markdown:
            try:
                full_result = analysis_result.model_dump(mode='json')
                export_markdown(full_result, args.export_markdown)
                print(f"✓ Markdown report saved to: {args.export_markdown}")

            except Exception as e:
                logger.error(f"Failed to export markdown: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
                return 1

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
                        return 1

            except Exception as e:
                logger.error(f"Failed to export graph: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
                return 1

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
        return 1


def handle_validate(args: argparse.Namespace) -> int:
    """
    Handle the validate subcommand - validates log file format without full analysis.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Validate input path
        try:
            input_path = validate_input_path(args.input)
            logger.info(f"Validating file: {input_path}")
        except PathValidationError as e:
            logger.error(f"Input validation failed: {e}")
            print(f"ERROR: {e}")
            return 1

        # Load and parse events
        try:
            raw_events = load_events_from_file(input_path, args.format)
            logger.info(f"Loaded {len(raw_events)} raw events")

            if not raw_events:
                print("WARNING: No events found in input file")
                return 0

            # Try to normalize events
            event_objects = [Event(**normalize_event(e)) for e in raw_events]

            print(f"✓ File validation successful!")
            print(f"  Format: {args.format}")
            print(f"  Events loaded: {len(raw_events)}")
            print(f"  Events normalized: {len(event_objects)}")

            # Show sample event
            if event_objects:
                print(f"\nSample event:")
                sample = event_objects[0]
                print(f"  Timestamp: {sample.timestamp}")
                print(f"  Severity: {sample.severity}")
                print(f"  Source: {sample.source}")
                print(f"  Message: {sample.message[:100]}..." if len(sample.message) > 100 else f"  Message: {sample.message}")

            return 0

        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
            print(f"ERROR: File validation failed - {e}")
            return 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
        return 1


def handle_export(args: argparse.Namespace) -> int:
    """
    Handle the export subcommand - exports existing analysis results to different formats.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Validate input file
        try:
            input_path = validate_input_path(args.input)
            logger.info(f"Loading analysis results from: {input_path}")
        except PathValidationError as e:
            logger.error(f"Input validation failed: {e}")
            print(f"ERROR: {e}")
            return 1

        # Load analysis results
        try:
            with open(input_path, 'r') as f:
                results = json.load(f)
            logger.info("Analysis results loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load results: {e}")
            print(f"ERROR: Failed to load analysis results - {e}")
            return 1

        # Determine output path
        if args.output:
            output_path = args.output
        else:
            # Auto-generate output filename
            stem = input_path.stem
            if args.format == "markdown":
                output_path = input_path.parent / f"{stem}.md"
            elif args.format == "mermaid":
                output_path = input_path.parent / f"{stem}.mmd"
            elif args.format == "dot":
                output_path = input_path.parent / f"{stem}.dot"
            else:
                output_path = input_path.parent / f"{stem}_export.json"

        # Export to requested format
        try:
            if args.format == "markdown":
                export_markdown(results, str(output_path))
                print(f"✓ Markdown report exported to: {output_path}")
            elif args.format == "mermaid":
                if 'causal_graph' not in results or not results['causal_graph']:
                    print("ERROR: No causal graph found in analysis results")
                    return 1
                export_graph_mermaid(results['causal_graph'], Path(output_path))
                print(f"✓ Mermaid graph exported to: {output_path}")
            elif args.format == "dot":
                if 'causal_graph' not in results or not results['causal_graph']:
                    print("ERROR: No causal graph found in analysis results")
                    return 1
                export_graph_dot(results['causal_graph'], Path(output_path))
                print(f"✓ DOT graph exported to: {output_path}")
            elif args.format == "json":
                export_json(results, str(output_path))
                print(f"✓ JSON exported to: {output_path}")
            else:
                print(f"ERROR: Unknown export format: {args.format}")
                return 1

            return 0

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
            print(f"ERROR: Export failed - {e}")
            return 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
        return 1


def handle_version(args: argparse.Namespace) -> int:
    """
    Handle the version subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    print(f"ADAPT-RCA version {__version__}")
    print("Advanced Diagnostic Agent for Proactive Troubleshooting - Root Cause Analyzer")

    if args.verbose:
        print(f"\nPython: {sys.version}")
        try:
            config = RCAConfig.load()
            print(f"LLM Provider: {config.llm_provider}")
            print(f"LLM Model: {config.llm_model}")
        except Exception:
            pass

    return 0


def handle_config(args: argparse.Namespace) -> int:
    """
    Handle the config subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        config = RCAConfig.load(args.config_file) if hasattr(args, 'config_file') and args.config_file else RCAConfig.load()

        if args.action == "validate":
            # Validate configuration
            try:
                config.validate()
                print("✓ Configuration is valid")
                return 0
            except Exception as e:
                print(f"ERROR: Configuration validation failed - {e}")
                return 1
        else:  # show
            # Display configuration
            print("Current ADAPT-RCA Configuration:")
            print(f"  LLM Provider: {config.llm_provider}")
            print(f"  LLM Model: {config.llm_model}")
            print(f"  Max Events: {config.max_events}")
            print(f"  Time Window: {config.time_window_minutes} minutes")

            if args.verbose:
                print("\nFull configuration:")
                config_dict = {
                    "llm_provider": config.llm_provider,
                    "llm_model": config.llm_model,
                    "max_events": config.max_events,
                    "time_window_minutes": config.time_window_minutes,
                }
                print(json.dumps(config_dict, indent=2))

            return 0

    except Exception as e:
        logger.error(f"Config operation failed: {e}", exc_info=args.debug if hasattr(args, 'debug') else False)
        print(f"ERROR: {e}")
        return 1


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser with subcommands.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="adapt-rca",
        description="ADAPT-RCA: Advanced Root Cause Analysis for logs and events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze logs (default subcommand)
  %(prog)s analyze logs.jsonl
  %(prog)s logs.jsonl                    # Backward compatible shorthand

  # Analyze with LLM
  %(prog)s analyze logs.jsonl --use-llm

  # Validate log file format
  %(prog)s validate system.log --format syslog

  # Export results to different formats
  %(prog)s export results.json markdown --output report.md
  %(prog)s export results.json mermaid

  # Show version and configuration
  %(prog)s version
  %(prog)s config show
  %(prog)s config validate

Environment Variables:
  ADAPT_RCA_LLM_PROVIDER   LLM provider (openai, anthropic, none)
  ADAPT_RCA_LLM_MODEL      Model to use (gpt-4, claude-3-opus, etc.)
  ADAPT_RCA_MAX_EVENTS     Maximum events to process (default: 5000)
  ADAPT_RCA_TIME_WINDOW    Time window in minutes (default: 15)
  OPENAI_API_KEY           OpenAI API key (if using openai provider)
  ANTHROPIC_API_KEY        Anthropic API key (if using anthropic provider)
        """
    )

    # Global flags (available to all subcommands)
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Enable quiet mode (only errors)"
    )
    parser.add_argument(
        "--config-file",
        metavar="PATH",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (overrides --verbose and --quiet)"
    )

    # Create subparsers
    subparsers = parser.add_subparsers(
        dest="subcommand",
        help="Available subcommands"
    )

    # ========================================
    # ANALYZE subcommand
    # ========================================
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze log files for root cause analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s logs.jsonl
  %(prog)s logs.csv --format csv --use-llm
  %(prog)s system.log --format syslog --output results.json
  %(prog)s access.log --format nginx --use-time-window --export-graph graph.mmd
        """
    )

    # Input/Output
    analyze_parser.add_argument(
        "input",
        help="Path to log file"
    )
    analyze_parser.add_argument(
        "--output", "-o",
        help="Path to write JSON results"
    )
    analyze_parser.add_argument(
        "--format", "-f",
        choices=["auto", "jsonl", "csv", "syslog", "text", "nginx", "apache", "generic"],
        default="auto",
        help="Input file format (default: auto-detect)"
    )

    # Analysis options
    analyze_parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM for analysis (requires LLM provider configured)"
    )
    analyze_parser.add_argument(
        "--use-time-window",
        action="store_true",
        help="Use time-window based event grouping (default: simple grouping)"
    )
    analyze_parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic", "none"],
        help="Override LLM provider (overrides ADAPT_RCA_LLM_PROVIDER)"
    )
    analyze_parser.add_argument(
        "--llm-model",
        help="Override LLM model (overrides ADAPT_RCA_LLM_MODEL)"
    )

    # Export options
    analyze_parser.add_argument(
        "--export-markdown",
        metavar="PATH",
        help="Export results as Markdown"
    )
    analyze_parser.add_argument(
        "--export-graph",
        metavar="PATH",
        help="Export causal graph (format based on extension: .mmd or .dot)"
    )

    analyze_parser.set_defaults(func=handle_analyze)

    # ========================================
    # VALIDATE subcommand
    # ========================================
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate log file format without performing analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s logs.jsonl
  %(prog)s system.log --format syslog
  %(prog)s access.log --format nginx
        """
    )

    validate_parser.add_argument(
        "input",
        help="Path to log file to validate"
    )
    validate_parser.add_argument(
        "--format", "-f",
        choices=["auto", "jsonl", "csv", "syslog", "text", "nginx", "apache", "generic"],
        default="auto",
        help="Input file format (default: auto-detect)"
    )

    validate_parser.set_defaults(func=handle_validate)

    # ========================================
    # EXPORT subcommand
    # ========================================
    export_parser = subparsers.add_parser(
        "export",
        help="Export existing analysis results to different formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s results.json markdown
  %(prog)s results.json mermaid --output graph.mmd
  %(prog)s results.json dot --output graph.dot
        """
    )

    export_parser.add_argument(
        "input",
        help="Path to analysis results JSON file"
    )
    export_parser.add_argument(
        "format",
        choices=["json", "markdown", "mermaid", "dot"],
        help="Export format"
    )
    export_parser.add_argument(
        "--output", "-o",
        help="Output file path (auto-generated if not specified)"
    )

    export_parser.set_defaults(func=handle_export)

    # ========================================
    # VERSION subcommand
    # ========================================
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information"
    )

    version_parser.set_defaults(func=handle_version)

    # ========================================
    # CONFIG subcommand
    # ========================================
    config_parser = subparsers.add_parser(
        "config",
        help="Show or validate configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s show
  %(prog)s validate
  %(prog)s show --verbose
        """
    )

    config_parser.add_argument(
        "action",
        nargs="?",
        choices=["show", "validate"],
        default="show",
        help="Config action (default: show)"
    )

    config_parser.set_defaults(func=handle_config)

    return parser


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()

    # Parse arguments, but handle backward compatibility
    # If first arg is not a known subcommand and looks like a file, treat it as analyze
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        known_subcommands = ['analyze', 'validate', 'export', 'version', 'config']

        # Check if it's a flag or looks like a file path (doesn't start with --)
        if (not first_arg.startswith('-') and
            first_arg not in known_subcommands and
            not first_arg in ['--help', '-h']):
            # Insert 'analyze' subcommand for backward compatibility
            sys.argv.insert(1, 'analyze')
            logger.debug("Backward compatibility: treating positional argument as 'analyze' subcommand")

    args = parser.parse_args()

    # Setup logging based on global flags
    setup_logging(
        verbose=args.verbose,
        quiet=args.quiet,
        debug=args.debug
    )

    # Check if a subcommand was provided
    if not hasattr(args, 'func'):
        # No subcommand provided, show help
        parser.print_help()
        sys.exit(1)

    # Call the appropriate handler function
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
