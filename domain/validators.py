"""
Validation helpers for playbook JSON schema and structure.
"""
from pydantic import ValidationError
from .models import PlaybookData


def validate_playbook(data: dict) -> PlaybookData:
    """Validate dict against PlaybookData schema; raises helpful error if invalid."""
    try:
        return PlaybookData.model_validate(data)
    except ValidationError as e:
        # Re-raise with a cleaner message for UI consumption
        raise ValueError(f"Playbook validation failed: {e}")