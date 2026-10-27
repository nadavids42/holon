"""Replaceable interpretation boundary and strict proposal validation."""
from dataclasses import dataclass
from typing import Protocol

OUTCOMES = ('supports', 'contradicts', 'unrelated', 'uncertain')
PROMPT_VERSION = 'report-relation-v2'


@dataclass(frozen=True)
class Interpretation:
    relation: str
    reason: str
    model: str
    prompt_version: str = PROMPT_VERSION

    @classmethod
    def validate(cls, value, model):
        if not isinstance(value, dict) or set(value) != {'relation', 'reason'}:
            raise ValueError('Model output must contain exactly relation and reason')
        if value['relation'] not in OUTCOMES:
            raise ValueError('Model returned an invalid relation')
        if not isinstance(value['reason'], str) or not value['reason'].strip():
            raise ValueError('Model reason must be a nonempty string')
        return cls(value['relation'], value['reason'].strip(), model)


class Interpreter(Protocol):
    def interpret(self, proposition: dict, report: str) -> Interpretation: ...
