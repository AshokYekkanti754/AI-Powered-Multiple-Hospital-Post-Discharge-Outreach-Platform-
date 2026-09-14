from __future__ import annotations
import json
from typing import Callable, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def parse_with_repair(raw: str | dict, schema: type[T], repair: Callable[[str, str], str] | None = None) -> T:
    try:
        value = raw if isinstance(raw, dict) else json.loads(raw)
        return schema.model_validate(value)
    except (ValueError, ValidationError, TypeError) as first_error:
        if repair is not None:
            try:
                repaired = repair(str(raw), schema.model_json_schema())
                return schema.model_validate(json.loads(repaired))
            except (ValueError, ValidationError, TypeError, json.JSONDecodeError):
                pass
        raise ValueError("AI output failed schema validation; escalate safely") from first_error
