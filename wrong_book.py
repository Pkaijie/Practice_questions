from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any

try:
    from .question_bank import Question
except ImportError:
    from question_bank import Question


DEFAULT_REMOVE_AFTER = 3


@dataclass
class WrongQuestionRecord:
    key: str
    stem: str
    answer: list[str]
    options: dict[str, str]
    number: str
    source_row: int
    question_type: str = ""
    sheet_name: str = ""
    correct_streak: int = 0
    wrong_count: int = 0
    last_wrong_answer: str = ""
    updated_at: float = 0

    @classmethod
    def from_question(cls, question: Question, key: str) -> "WrongQuestionRecord":
        return cls(
            key=key,
            stem=question.stem,
            answer=list(question.answer),
            options=dict(question.options),
            number=question.number,
            source_row=question.source_row,
            question_type=question.question_type,
            sheet_name=question.sheet_name,
            updated_at=time.time(),
        )

    @classmethod
    def from_dict(cls, key: str, data: dict[str, Any]) -> "WrongQuestionRecord":
        options = data.get("options")
        if not isinstance(options, dict):
            options = {}
        answer = data.get("answer", [])
        if isinstance(answer, str):
            answer = [answer] if answer else []
        elif isinstance(answer, list):
            answer = [str(item) for item in answer]
        else:
            answer = []

        return cls(
            key=key,
            stem=str(data.get("stem", "")),
            answer=answer,
            options={str(k): str(v) for k, v in options.items()},
            number=str(data.get("number", "")),
            source_row=_safe_int(data.get("source_row"), 0),
            question_type=str(data.get("question_type", "")),
            sheet_name=str(data.get("sheet_name", "")),
            correct_streak=max(0, _safe_int(data.get("correct_streak"), 0)),
            wrong_count=max(0, _safe_int(data.get("wrong_count"), 0)),
            last_wrong_answer=str(data.get("last_wrong_answer", "")),
            updated_at=float(data.get("updated_at", 0) or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "stem": self.stem,
            "answer": self.answer,
            "options": self.options,
            "number": self.number,
            "source_row": self.source_row,
            "question_type": self.question_type,
            "sheet_name": self.sheet_name,
            "correct_streak": self.correct_streak,
            "wrong_count": self.wrong_count,
            "last_wrong_answer": self.last_wrong_answer,
            "updated_at": self.updated_at,
        }


class WrongBook:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.remove_after = DEFAULT_REMOVE_AFTER
        self.records: dict[str, WrongQuestionRecord] = {}
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

        self.remove_after = _normalize_threshold(data.get("remove_after", DEFAULT_REMOVE_AFTER))
        items = data.get("items", {})
        if not isinstance(items, dict):
            return

        self.records = {
            str(key): WrongQuestionRecord.from_dict(str(key), value)
            for key, value in items.items()
            if isinstance(value, dict)
        }

    def save(self) -> bool:
        self.last_save_ok = False
        self.last_error = ""
        data = {
            "version": 1,
            "remove_after": self.remove_after,
            "items": {
                key: record.to_dict()
                for key, record in sorted(
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

    def set_remove_after(self, value: int) -> bool:
        self.remove_after = _normalize_threshold(value)
        return self.save()

    def key_for(self, question: Question) -> str:
        return question_key(question)

    def _stored_key_for(self, question: Question) -> str:
        key = self.key_for(question)
        if key in self.records:
            return key
        legacy_key = legacy_question_key(question)
        if legacy_key in self.records:
            return legacy_key
        return key

    def has(self, question: Question) -> bool:
        return self._stored_key_for(question) in self.records

    def count_for(self, questions: list[Question]) -> int:
        return sum(1 for question in questions if self.has(question))

    def questions_from(self, questions: list[Question]) -> list[Question]:
        return [question for question in questions if self.has(question)]

    def record_for(self, question: Question) -> WrongQuestionRecord | None:
        return self.records.get(self._stored_key_for(question))

    def mark_wrong(self, question: Question, selected_answer: str) -> WrongQuestionRecord:
        key = self._stored_key_for(question)
        record = self.records.get(key) or WrongQuestionRecord.from_question(question, key)
        record.stem = question.stem
        record.answer = list(question.answer)
        record.options = dict(question.options)
        record.number = question.number
        record.source_row = question.source_row
        record.question_type = question.question_type
        record.sheet_name = question.sheet_name
        record.correct_streak = 0
        record.wrong_count += 1
        record.last_wrong_answer = selected_answer
        record.updated_at = time.time()
        self.records[key] = record
        self.save()
        return record

    def mark_correct(self, question: Question) -> tuple[int, bool]:
        key = self._stored_key_for(question)
        record = self.records.get(key)
        if record is None:
            return 0, False

        record.correct_streak += 1
        record.updated_at = time.time()
        streak = record.correct_streak
        removed = streak >= self.remove_after
        if removed:
            del self.records[key]
        self.save()
        return streak, removed

    def clear_for(self, questions: list[Question] | None = None) -> int:
        if questions is None:
            removed = len(self.records)
            self.records.clear()
            self.save()
            return removed

        keys = {self.key_for(question) for question in questions}
        keys.update(legacy_question_key(question) for question in questions)
        removed = 0
        for key in list(self.records):
            if key in keys:
                removed += 1
                del self.records[key]
        self.save()
        return removed


def question_key(question: Question) -> str:
    payload = {
        "question_type": question.question_type,
        "stem": _normalize_text(question.stem),
        "answer": [letter.strip().upper() for letter in question.answer],
        "options": {
            letter: _normalize_text(text)
            for letter, text in sorted(question.options.items())
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def legacy_question_key(question: Question) -> str:
    legacy_answer = question.answer[0] if len(question.answer) == 1 else "".join(question.answer)
    payload = {
        "stem": _normalize_text(question.stem),
        "answer": legacy_answer.strip().upper(),
        "options": {
            letter: _normalize_text(text)
            for letter, text in sorted(question.options.items())
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_threshold(value: object) -> int:
    return min(10, max(1, _safe_int(value, DEFAULT_REMOVE_AFTER)))


def _safe_int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split())
