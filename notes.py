from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

try:
    from .question_bank import Question
    from .wrong_book import legacy_question_key, question_key
except ImportError:
    from question_bank import Question
    from wrong_book import legacy_question_key, question_key


@dataclass
class QuestionNote:
    text: str
    updated_at: float = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuestionNote":
        return cls(
            text=str(data.get("text", "")),
            updated_at=float(data.get("updated_at", 0) or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "updated_at": self.updated_at,
        }


class QuestionNotes:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.records: dict[str, QuestionNote] = {}
        self.last_save_ok = True
        self.last_error = ""
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return

        items = data.get("items", {})
        if not isinstance(items, dict):
            return

        self.records = {
            str(key): QuestionNote.from_dict(value)
            for key, value in items.items()
            if isinstance(value, dict)
        }

    def save(self) -> bool:
        self.last_save_ok = False
        self.last_error = ""
        data = {
            "version": 1,
            "items": {
                key: note.to_dict()
                for key, note in sorted(
                    self.records.items(),
                    key=lambda item: item[1].updated_at,
                    reverse=True,
                )
            },
        }
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(self.path)
        except OSError as exc:
            self.last_error = str(exc)
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            return False

        self.last_save_ok = True
        return True

    def note_for(self, question: Question) -> str:
        note = self.records.get(self._stored_key_for(question))
        return note.text if note else ""

    def set_note(self, question: Question, text: str) -> bool:
        key = self._stored_key_for(question)
        note_text = text.strip()
        if note_text:
            self.records[key] = QuestionNote(text=note_text, updated_at=time.time())
        else:
            self.records.pop(key, None)
            self.records.pop(legacy_question_key(question), None)
        return self.save()

    def _stored_key_for(self, question: Question) -> str:
        key = question_key(question)
        if key in self.records:
            return key
        legacy_key = legacy_question_key(question)
        if legacy_key in self.records:
            return legacy_key
        return key
