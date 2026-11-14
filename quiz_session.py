from __future__ import annotations

from dataclasses import dataclass, field
import random

try:
    from .question_bank import Question
except ImportError:
    from question_bank import Question


MODE_ALL = "all"
MODE_WRONG = "wrong"
ORDER_RANDOM = "random"
ORDER_SEQUENTIAL = "sequential"


@dataclass
class QuizSession:
    questions: list[Question] = field(default_factory=list)
    mode: str = MODE_ALL
    order_mode: str = ORDER_RANDOM
    type_filter: str = MODE_ALL
    current_index: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    answered: bool = False

    @classmethod
    def start(
        cls,
        questions: list[Question],
        mode: str,
        order_mode: str = ORDER_RANDOM,
        type_filter: str = MODE_ALL,
    ) -> "QuizSession":
        order = list(questions)
        if order_mode == ORDER_RANDOM:
            random.shuffle(order)
        return cls(questions=order, mode=mode, order_mode=order_mode, type_filter=type_filter)

    @classmethod
    def restore(
        cls,
        questions: list[Question],
        mode: str,
        order_mode: str,
        type_filter: str,
        current_index: int,
        correct_count: int,
        wrong_count: int,
    ) -> "QuizSession":
        if questions:
            current_index = max(0, min(current_index, len(questions) - 1))
        else:
            current_index = 0
        return cls(
            questions=list(questions),
            mode=mode,
            order_mode=order_mode,
            type_filter=type_filter,
            current_index=current_index,
            correct_count=max(0, correct_count),
            wrong_count=max(0, wrong_count),
        )

    @classmethod
    def empty(cls, mode: str = MODE_ALL, type_filter: str = MODE_ALL) -> "QuizSession":
        return cls(mode=mode, type_filter=type_filter)

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def answered_count(self) -> int:
        return self.correct_count + self.wrong_count

    @property
    def has_questions(self) -> bool:
        return bool(self.questions)

    @property
    def has_next(self) -> bool:
        return self.current_index < self.total - 1

    @property
    def current_question(self) -> Question | None:
        if not self.questions:
            return None
        return self.questions[self.current_index]

    def record_answer(self, is_correct: bool) -> None:
        self.answered = True
        if is_correct:
            self.correct_count += 1
        else:
            self.wrong_count += 1

    def next_question(self) -> bool:
        if not self.answered or not self.has_next:
            return False
        self.current_index += 1
        self.answered = False
        return True
