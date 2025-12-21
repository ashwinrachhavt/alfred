from __future__ import annotations

from typing import Any

from bson import ObjectId
from pydantic_core import core_schema


class _ObjectIdOrStr(ObjectId):
    """Pydantic-friendly ObjectId type.

    Accept either a `bson.ObjectId` instance or a valid 24-char hex string and normalize to
    `bson.ObjectId`. Serializes to a hex string for JSON output.
    """

    @classmethod
    def _validate(cls, value: Any) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        if isinstance(value, str) and ObjectId.is_valid(value):
            return ObjectId(value)
        raise TypeError("Not a valid ObjectId or ObjectId hex string")

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: Any
    ) -> core_schema.CoreSchema:
        serializer = core_schema.plain_serializer_function_ser_schema(
            lambda value: str(value),
            return_schema=core_schema.str_schema(),
        )
        validated = core_schema.no_info_plain_validator_function(
            cls._validate,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=serializer,
        )
        return core_schema.json_or_python_schema(json_schema=validated, python_schema=validated)


__all__ = ["_ObjectIdOrStr"]
