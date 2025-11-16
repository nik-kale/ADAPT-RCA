import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import RCAConfig
from .ingestion.file_loader import load_jsonl
from .parsing.log_parser import normalize_event
from .reasoning.heuristics import simple_grouping
from .reasoning.agent import analyze_incident
from .reporting.formatter import format_human_readable
from .utils import validate_input_path, validate_output_path, PathValidationError

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ADAPT-RCA: Root Cause Analysis for logs and events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input logs.jsonl
  %(prog)s --input logs.jsonl --output results.json
  %(prog)s --input logs.jsonl --output report.json --verbose
        """
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to JSONL log file"
    )
    parser.add_argument(
        "--output",
        help="Path to write JSON result (optional)"
    )
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
    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, debug=args.debug)

    try:
        # Validate and load configuration
        config = RCAConfig()
        config.validate()
        logger.debug(f"Configuration: {config}")

        # Validate input path
        try:
            input_path = validate_input_path(args.input)
            logger.info(f"Loading events from: {input_path}")
        except PathValidationError as e:
            logger.error(f"Input validation failed: {e}")
            sys.exit(1)

        # Load and normalize events
        try:
            raw_events = list(load_jsonl(input_path))
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

            events = [normalize_event(e) for e in raw_events]
            logger.info(f"Normalized {len(events)} events")

        except Exception as e:
            logger.error(f"Failed to load events: {e}", exc_info=args.debug)
            sys.exit(1)

        # Group events into incidents
        try:
            incident_groups = simple_grouping(events)
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
            # Safely get first group or empty list
            events_to_analyze = incident_groups[0] if incident_groups else []
            result = analyze_incident(events_to_analyze)
            logger.info("Analysis complete")

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=args.debug)
            sys.exit(1)

        # Display results
        print(format_human_readable(result))

        # Save to file if requested
        if args.output:
            try:
                output_path = validate_output_path(
                    args.output,
                    allow_overwrite=True,
                    allowed_extensions={'.json'}
                )
                output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
                logger.info(f"Results written to: {output_path}")

            except PathValidationError as e:
                logger.error(f"Output validation failed: {e}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Failed to write output: {e}", exc_info=args.debug)
                sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=args.debug)
        sys.exit(1)


if __name__ == "__main__":
    main()
