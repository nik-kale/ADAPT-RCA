from typing import Dict

from ..exceptions import LogParseError, ValidationError


def normalize_event(raw: Dict) -> Dict:
    """
    Normalizes a raw log record into a common event schema.
    
    Args:
        raw: Raw log event dictionary
        
    Returns:
        Normalized event dictionary
        
    Raises:
        LogParseError: If raw event is invalid
        ValidationError: If required fields are missing
    """
    if not isinstance(raw, dict):
        raise LogParseError(f"Event must be a dictionary, got {type(raw).__name__}")
    
    # Extract and validate fields
    try:
        normalized = {
            "timestamp": raw.get("timestamp"),
            "service": raw.get("service") or raw.get("component"),
            "level": raw.get("level") or raw.get("severity"),
            "message": raw.get("message"),
            "raw": raw,
        }
        
        # Validate at least some useful data exists
        if not any([normalized["service"], normalized["message"]]):
            raise ValidationError(
                "Event must have at least 'service' or 'message' field"
            )
        
        return normalized
        
    except (AttributeError, KeyError) as e:
        raise LogParseError(f"Failed to parse event: {e}") from e
