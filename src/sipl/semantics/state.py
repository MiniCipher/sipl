"""States: partial mappings of variable names to integers (номінативні дані)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

State = dict[str, int]

_PAIR = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|:=|->|↦|:)\s*([+-]?\d+)\s*")


class StateFormatError(ValueError):
    pass


def parse_state(text: str) -> State:
    """Parse ``"X=2, Y=3"`` (also ``X:=2 Y->3``, ``[X ↦ 2]``) or a JSON object."""
    text = text.strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StateFormatError(f"некоректний JSON стану: {exc}") from None
        return state_from_json(data)
    text = text.strip("[]")
    state: State = {}
    for chunk in re.split(r"[,;\s]+(?=[A-Za-z_])", text):
        if not chunk.strip():
            continue
        m = _PAIR.fullmatch(chunk.strip().rstrip(",;"))
        if not m:
            raise StateFormatError(
                f"не вдалося розібрати '{chunk.strip()}': очікувалось ІМ'Я=ціле, напр. X=2")
        state[m.group(1)] = int(m.group(2))
    return state


def state_from_json(data: object) -> State:
    if not isinstance(data, Mapping):
        raise StateFormatError("стан має бути JSON-об'єктом {\"X\": 2}")
    out: State = {}
    for k, v in data.items():
        if not isinstance(v, int) or isinstance(v, bool):
            raise StateFormatError(f"значення змінної {k} має бути цілим числом")
        out[str(k)] = v
    return out


def format_state(state: Mapping[str, int] | None, style: str = "unicode") -> str:
    if state is None:
        return "⊥" if style == "unicode" else "undefined"
    arrow = " ↦ " if style == "unicode" else " -> "
    return "[" + ", ".join(f"{k}{arrow}{v}" for k, v in state.items()) + "]"
