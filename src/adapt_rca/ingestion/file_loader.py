from pathlib import Path
from typing import Iterable, Dict
import json
import logging

from ..exceptions import FileLoadError, InvalidFormatError

logger = logging.getLogger(__name__)


def load_jsonl(path: str | Path) -> Iterable[Dict]:
    """
    Load JSONL file line by line.
    
    Args:
        path: Path to JSONL file
        
    Yields:
        Parsed JSON objects
        
    Raises:
        FileLoadError: If file cannot be opened
        InvalidFormatError: If file format is invalid
    """
    path = Path(path)
    
    if not path.exists():
        raise FileLoadError(f"File not found: {path}")
    
    if not path.is_file():
        raise FileLoadError(f"Not a file: {path}")
    
    try:
        with path.open() as f:
            line_number = 0
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Skipping invalid JSON at line {line_number}: {e}"
                    )
                    continue
    except OSError as e:
        raise FileLoadError(f"Failed to read file {path}: {e}") from e
    except UnicodeDecodeError as e:
        raise InvalidFormatError(f"Invalid file encoding: {e}") from e
