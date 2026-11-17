"""Canonical serialization for signed evidence records.

Format: UTF-8 JSON, keys sorted lexicographically, no whitespace, no floats
(integers, strings, booleans, null, arrays, objects only). For float-free data this
is byte-identical to RFC 8785 (JCS) output, so independent verifiers can reproduce it.
"""
import json


class CanonicalizationError(ValueError):
    pass


def _check(v, path="$"):
    if isinstance(v, float):
        raise CanonicalizationError(f"floats not allowed in signed records ({path})")
    if isinstance(v, dict):
        for k, x in v.items():
            if not isinstance(k, str):
                raise CanonicalizationError(f"non-string key at {path}")
            _check(x, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _check(x, f"{path}[{i}]")
    elif not isinstance(v, (str, int, bool, type(None))):
        raise CanonicalizationError(f"unsupported type {type(v).__name__} at {path}")


def canonical_bytes(record: dict) -> bytes:
    """Bytes that are signed: the record without its `signature` field."""
    body = {k: v for k, v in record.items() if k != "signature"}
    _check(body)
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
