from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import posixpath
import re
from typing import Iterable
import xml.etree.ElementTree as ET
import zipfile


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_TAG = f"{{{REL_NS}}}id"
LETTERS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

TYPE_SINGLE = "single"
TYPE_MULTI = "multi"
TYPE_JUDGE = "judge"

QUESTION_TYPE_NAMES = {
    TYPE_SINGLE: "单选题",
    TYPE_MULTI: "多选题",
    TYPE_JUDGE: "判断题",
}

SHEET_TYPE_HINTS = {
    "单选题": TYPE_SINGLE,
    "单项选择题": TYPE_SINGLE,
    "多选题": TYPE_MULTI,
    "多项选择题": TYPE_MULTI,
    "判断题": TYPE_JUDGE,
}


@dataclass(frozen=True)
class Question:
    number: str
    stem: str
    answer: tuple[str, ...]
    options: dict[str, str]
    source_row: int
    question_type: str = TYPE_SINGLE
    sheet_name: str = ""


@dataclass(frozen=True)
class QuestionBank:
    path: Path
    sheet_name: str
    questions: list[Question]
    skipped_rows: list[str]


@dataclass(frozen=True)
class SheetInfo:
    name: str
    path: str


class QuestionImportError(Exception):
    """Raised when an Excel file cannot be used as a question bank."""


def read_question_bank(path: str | Path, sheet_name: str | None = None) -> QuestionBank:
    """Read single-choice, multiple-choice, and true/false questions from an xlsx file."""

    excel_path = Path(path)
    if not excel_path.exists():
        raise QuestionImportError(f"找不到 Excel 文件：{excel_path}")
    if excel_path.suffix.lower() != ".xlsx":
        raise QuestionImportError("目前仅支持 .xlsx 文件。")

    try:
        with zipfile.ZipFile(excel_path) as archive:
            shared_strings = _read_shared_strings(archive)
            sheets = _read_sheets(archive)
            candidates = _select_candidate_sheets(sheets, sheet_name)

            all_questions: list[Question] = []
            all_skipped_rows: list[str] = []
            last_error: Exception | None = None
            used_sheet_names: list[str] = []

            for sheet in candidates:
                try:
                    rows = _read_rows(archive, sheet.path, shared_strings)
                    questions, skipped_rows = _build_questions(rows, sheet.name)
                    if questions:
                        all_questions.extend(questions)
                        all_skipped_rows.extend(skipped_rows)
                        used_sheet_names.append(sheet.name)
                except QuestionImportError as exc:
                    last_error = exc

            if all_questions:
                return QuestionBank(
                    path=excel_path,
                    sheet_name="、".join(used_sheet_names),
                    questions=all_questions,
                    skipped_rows=all_skipped_rows,
                )

            if last_error:
                raise last_error
            raise QuestionImportError("没有在工作簿中找到可导入的题目。")
    except zipfile.BadZipFile as exc:
        raise QuestionImportError("Excel 文件损坏，无法读取。") from exc
    except KeyError as exc:
        raise QuestionImportError(f"Excel 文件缺少必要结构，无法读取：{exc}") from exc
    except ET.ParseError as exc:
        raise QuestionImportError(f"Excel 文件内部 XML 损坏，无法读取：{exc}") from exc
    except OSError as exc:
        raise QuestionImportError(f"读取 Excel 文件失败：{exc}") from exc


def load_questions_from_xlsx(path: str | Path, sheet_name: str | None = None) -> list[Question]:
    return read_question_bank(path, sheet_name).questions


def question_type_name(question: Question) -> str:
    return QUESTION_TYPE_NAMES.get(question.question_type, "题目")


def format_answer(question: Question) -> str:
    parts = [
        f"{letter}. {question.options.get(letter, '')}".rstrip()
        for letter in question.answer
    ]
    return "；".join(parts)


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        parts = [node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")]
        strings.append("".join(parts))
    return strings


def _read_sheets(archive: zipfile.ZipFile) -> list[SheetInfo]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relation_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships
        if rel.attrib.get("Id") and rel.attrib.get("Target")
    }

    sheets: list[SheetInfo] = []
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        relation_id = sheet.attrib.get(REL_TAG)
        target = relation_targets.get(relation_id or "")
        if not target:
            continue
        if target.startswith("/"):
            sheet_path = target.lstrip("/")
        else:
            sheet_path = posixpath.normpath(posixpath.join("xl", target))
        sheets.append(SheetInfo(name=sheet.attrib.get("name", ""), path=sheet_path))

    if not sheets:
        raise QuestionImportError("Excel 工作簿中没有可读取的工作表。")
    return sheets


def _select_candidate_sheets(sheets: list[SheetInfo], sheet_name: str | None) -> list[SheetInfo]:
    if sheet_name:
        matches = [sheet for sheet in sheets if sheet.name == sheet_name]
        if not matches:
            raise QuestionImportError(f"找不到名为“{sheet_name}”的工作表。")
        return matches

    priority = ("单选题", "多选题", "判断题")
    known_sheets = [sheet for name in priority for sheet in sheets if sheet.name == name]
    if known_sheets:
        return known_sheets
    return sheets


def _read_rows(
    archive: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[tuple[int, list[str]]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows: list[tuple[int, list[str]]] = []

    for fallback_row_index, row_node in enumerate(
        root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"),
        start=1,
    ):
        row_number = _safe_int(row_node.attrib.get("r"), fallback_row_index)
        values: list[str] = []
        for fallback_col_index, cell in enumerate(row_node.findall(f"{{{MAIN_NS}}}c")):
            col_index = _column_index(cell.attrib.get("r"), fallback_col_index)
            while len(values) <= col_index:
                values.append("")
            values[col_index] = _cell_text(cell, shared_strings)
        rows.append((row_number, values))

    return rows


def _build_questions(rows: list[tuple[int, list[str]]], sheet_name: str) -> tuple[list[Question], list[str]]:
    header_position, columns, question_type = _find_header(rows, sheet_name)
    skipped_rows: list[str] = []
    questions: list[Question] = []

    for row_number, row in rows[header_position + 1 :]:
        stem = _clean_text(_value_at(row, columns["question"]))
        if not stem:
            continue

        if question_type == TYPE_JUDGE:
            options = {"A": "正确", "B": "错误"}
            answer = _normalize_judge_answer(_value_at(row, columns["answer"]))
        else:
            options = {
                letter: _clean_text(_value_at(row, index))
                for letter, index in columns["options"].items()
                if _clean_text(_value_at(row, index))
            }
            if len(options) < 2:
                skipped_rows.append(f"{sheet_name} 第 {row_number} 行：选项少于 2 个，已跳过。")
                continue
            answer = _normalize_choice_answer(_value_at(row, columns["answer"]), options, question_type)

        if not answer:
            skipped_rows.append(f"{sheet_name} 第 {row_number} 行：正确答案为空或无法识别，已跳过。")
            continue

        number = _clean_text(_value_at(row, columns.get("number", -1)))
        questions.append(
            Question(
                number=number,
                stem=stem,
                answer=answer,
                options=options,
                source_row=row_number,
                question_type=question_type,
                sheet_name=sheet_name,
            )
        )

    if not questions:
        raise QuestionImportError(f"{sheet_name} 没有读到有效题目，请检查表头和题目内容。")

    return questions, skipped_rows


def _find_header(rows: list[tuple[int, list[str]]], sheet_name: str) -> tuple[int, dict[str, object], str]:
    sheet_type = _infer_sheet_type(sheet_name)

    for row_index, (_row_number, row) in enumerate(rows[:50]):
        header_map = {_normalize_header(value): index for index, value in enumerate(row) if value}
        question_index = _first_index(header_map, ("题干", "题目", "问题"))
        answer_index = _first_index(header_map, ("正确答案", "答案"))
        number_index = _first_index(header_map, ("序号", "编号", "题号"))
        option_columns = _find_option_columns(row)

        if question_index is None or answer_index is None:
            continue

        question_type = sheet_type
        if question_type is None:
            question_type = TYPE_JUDGE if not option_columns else TYPE_SINGLE

        if question_type != TYPE_JUDGE and len(option_columns) < 2:
            continue

        columns: dict[str, object] = {
            "question": question_index,
            "answer": answer_index,
            "options": option_columns,
        }
        if number_index is not None:
            columns["number"] = number_index
        return row_index, columns, question_type

    raise QuestionImportError(f"{sheet_name} 未找到题库表头，需要包含：题干、正确答案。")


def _infer_sheet_type(sheet_name: str) -> str | None:
    normalized = _normalize_header(sheet_name)
    if "多" in normalized:
        return TYPE_MULTI
    if "判断" in normalized:
        return TYPE_JUDGE
    if "单" in normalized:
        return TYPE_SINGLE
    return SHEET_TYPE_HINTS.get(sheet_name)


def _find_option_columns(row: Iterable[str]) -> dict[str, int]:
    option_columns: dict[str, int] = {}
    for index, value in enumerate(row):
        header = _normalize_header(value)
        match = re.fullmatch(r"(?:选项)?([A-Z])(?:选项)?", header)
        if match and match.group(1) in LETTERS:
            option_columns[match.group(1)] = index
    return dict(sorted(option_columns.items()))


def _first_index(header_map: dict[str, int], candidates: Iterable[str]) -> int | None:
    for candidate in candidates:
        index = header_map.get(_normalize_header(candidate))
        if index is not None:
            return index
    return None


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t"))

    value_node = cell.find(f"{{{MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return ""

    value = value_node.text
    if cell_type == "s":
        index = _safe_int(value, -1)
        if 0 <= index < len(shared_strings):
            return shared_strings[index]
    if cell_type == "b":
        return "是" if value == "1" else "否"
    return value


def _normalize_choice_answer(value: str, options: dict[str, str], question_type: str) -> tuple[str, ...]:
    raw_answer = _clean_text(value)
    if not raw_answer:
        return ()

    letters = _extract_answer_letters(raw_answer)
    letters = tuple(letter for letter in letters if letter in options)

    if not letters and question_type == TYPE_SINGLE:
        for letter, option_text in options.items():
            if _clean_text(option_text) == raw_answer:
                letters = (letter,)
                break

    if question_type == TYPE_SINGLE and len(letters) != 1:
        return ()
    if question_type == TYPE_MULTI and len(letters) < 2:
        return ()
    return letters


def _extract_answer_letters(value: str) -> tuple[str, ...]:
    normalized = _to_half_width(value).upper()
    normalized = re.sub(r"(正确答案|答案|选项)[:：]?", "", normalized)
    normalized = re.sub(r"[\(\)\[\]\{\}.。:：、，,;；/\\|+&\s]+", ";", normalized)
    parts = [part for part in normalized.split(";") if part]

    if len(parts) == 1 and re.fullmatch(r"[A-Z]+", parts[0]):
        parts = list(parts[0])

    letters: list[str] = []
    for part in parts:
        match = re.fullmatch(r"([A-Z])", part)
        if match and match.group(1) not in letters:
            letters.append(match.group(1))
    return tuple(letter for letter in LETTERS if letter in letters)


def _normalize_judge_answer(value: str) -> tuple[str, ...]:
    normalized = _normalize_header(value)
    if normalized in {"正确", "对", "是", "TRUE", "T", "1", "√", "YES", "Y", "A"}:
        return ("A",)
    if normalized in {"错误", "错", "否", "FALSE", "F", "0", "×", "X", "NO", "N", "B"}:
        return ("B",)
    return ()


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", "", _to_half_width(str(value))).upper()


def _clean_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _value_at(row: list[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return row[index]


def _column_index(cell_reference: str | None, fallback: int) -> int:
    if not cell_reference:
        return fallback
    letters = re.match(r"[A-Za-z]+", cell_reference)
    if not letters:
        return fallback

    index = 0
    for char in letters.group(0).upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _safe_int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _to_half_width(value: str) -> str:
    chars: list[str] = []
    for char in value:
        code = ord(char)
        if code == 0x3000:
            chars.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            chars.append(chr(code - 0xFEE0))
        else:
            chars.append(char)
    return "".join(chars)


if __name__ == "__main__":
    default_path = Path(__file__).with_name("practice.xlsx")
    bank = read_question_bank(default_path)
    print(f"导入 {len(bank.questions)} 道题，工作表：{bank.sheet_name}")
