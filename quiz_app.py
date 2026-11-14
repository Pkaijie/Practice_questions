from __future__ import annotations

import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from .question_bank import (
        TYPE_JUDGE,
        TYPE_MULTI,
        TYPE_SINGLE,
        Question,
        QuestionBank,
        QuestionImportError,
        format_answer,
        question_type_name,
        read_question_bank,
    )
    from .notes import QuestionNotes
    from .quiz_session import MODE_ALL, MODE_WRONG, ORDER_RANDOM, ORDER_SEQUENTIAL, QuizSession
    from .wrong_book import WrongBook, question_key
except ImportError:
    from question_bank import (
        TYPE_JUDGE,
        TYPE_MULTI,
        TYPE_SINGLE,
        Question,
        QuestionBank,
        QuestionImportError,
        format_answer,
        question_type_name,
        read_question_bank,
    )
    from notes import QuestionNotes
    from quiz_session import MODE_ALL, MODE_WRONG, ORDER_RANDOM, ORDER_SEQUENTIAL, QuizSession
    from wrong_book import WrongBook, question_key


APP_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
DATA_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else APP_DIR
WRONG_BOOK_PATH = DATA_DIR / "wrong_book.json"
NOTES_PATH = DATA_DIR / "notes.json"
CONFIG_PATH = DATA_DIR / "app_config.json"
BUNDLED_BANK_PREFIX = "bundled:"

ORDER_MODE_LABELS = {
    ORDER_RANDOM: "随机刷题",
    ORDER_SEQUENTIAL: "顺序刷题",
}
ORDER_MODE_VALUES = {label: value for value, label in ORDER_MODE_LABELS.items()}

TYPE_FILTER_LABELS = {
    MODE_ALL: "全部题型",
    TYPE_SINGLE: "单选题",
    TYPE_MULTI: "多选题",
    TYPE_JUDGE: "判断题",
}
TYPE_FILTER_VALUES = {label: value for value, label in TYPE_FILTER_LABELS.items()}


class QuizApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("刷题软件")
        self.geometry("960x680")
        self.minsize(820, 560)

        self.bank: QuestionBank | None = None
        self.wrong_book = WrongBook(WRONG_BOOK_PATH)
        self.notes = QuestionNotes(NOTES_PATH)
        self.questions: list[Question] = []
        self.session = QuizSession.empty()
        self.selected_answer = tk.StringVar(value="")
        self.option_buttons: dict[str, tk.Widget] = {}
        self.multi_answer_vars: dict[str, tk.BooleanVar] = {}
        self.note_save_after_id: str | None = None
        self.note_editor_visible = False

        self._create_vars()
        self._configure_style()
        self._build_layout()
        self._bind_events()

        self._load_initial_bank()

    def _create_vars(self) -> None:
        self.file_var = tk.StringVar(value="未导入")
        self.app_title_var = tk.StringVar(value="刷题软件")
        self.sheet_var = tk.StringVar(value="-")
        self.total_var = tk.StringVar(value="0")
        self.wrong_book_count_var = tk.StringVar(value="0")
        self.mode_var = tk.StringVar(value="全部题目")
        self.order_mode_var = tk.StringVar(value=ORDER_MODE_LABELS[ORDER_RANDOM])
        self.type_filter_var = tk.StringVar(value=TYPE_FILTER_LABELS[MODE_ALL])
        self.remove_after_var = tk.IntVar(value=self.wrong_book.remove_after)
        self.progress_var = tk.StringVar(value="-")
        self.answered_var = tk.StringVar(value="0")
        self.correct_var = tk.StringVar(value="0")
        self.rate_var = tk.StringVar(value="0%")
        self.question_number_var = tk.StringVar(value="")
        self.question_text_var = tk.StringVar(value="")
        self.feedback_var = tk.StringVar(value="")
        self.note_status_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="请选择 Excel 题库。")

    def _configure_style(self) -> None:
        self.configure(bg="#f4f6f8")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background="#f4f6f8")
        style.configure("Panel.TFrame", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("TLabel", background="#f4f6f8", foreground="#1f2937", font=("Microsoft YaHei UI", 10))
        style.configure("Panel.TLabel", background="#ffffff", foreground="#1f2937", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background="#f4f6f8", foreground="#111827", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Question.TLabel", background="#ffffff", foreground="#111827", font=("Microsoft YaHei UI", 14))
        style.configure("Meta.TLabel", background="#ffffff", foreground="#64748b", font=("Microsoft YaHei UI", 9))
        style.configure("Feedback.TLabel", background="#ffffff", foreground="#0f766e", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Danger.TLabel", background="#ffffff", foreground="#b91c1c", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 7))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(14, 8))
        style.configure("Horizontal.TProgressbar", thickness=10)

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=22, style="App.TFrame")
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root, style="App.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, textvariable=self.app_title_var, style="Title.TLabel").pack(side=tk.LEFT)

        actions = ttk.Frame(header, style="App.TFrame")
        actions.pack(side=tk.RIGHT)
        ttk.Button(actions, text="导入 Excel", command=self._choose_file).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="练习错题", command=self._start_wrong_quiz).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="重新开始", command=self._restart_quiz).pack(side=tk.LEFT)

        body = ttk.Frame(root, style="App.TFrame")
        body.pack(fill=tk.BOTH, expand=True, pady=(18, 10))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        body.rowconfigure(0, weight=1)

        self.question_panel = ttk.Frame(body, padding=22, style="Panel.TFrame")
        self.question_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.question_panel.columnconfigure(0, weight=1)
        self.question_panel.rowconfigure(1, weight=1)

        top_line = ttk.Frame(self.question_panel, style="Panel.TFrame")
        top_line.grid(row=0, column=0, sticky="ew")
        ttk.Label(top_line, textvariable=self.progress_var, style="Meta.TLabel").pack(side=tk.LEFT)
        ttk.Label(top_line, textvariable=self.question_number_var, style="Meta.TLabel").pack(side=tk.RIGHT)

        self.content_canvas = tk.Canvas(
            self.question_panel,
            bg="#ffffff",
            highlightthickness=0,
            borderwidth=0,
        )
        self.content_scrollbar = ttk.Scrollbar(
            self.question_panel,
            orient=tk.VERTICAL,
            command=self.content_canvas.yview,
        )
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)
        self.content_canvas.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        self.content_scrollbar.grid(row=1, column=1, sticky="ns", pady=(18, 0))

        self.scroll_content = tk.Frame(self.content_canvas, bg="#ffffff")
        self.scroll_window = self.content_canvas.create_window((0, 0), window=self.scroll_content, anchor=tk.NW)
        self.scroll_content.bind("<Configure>", self._sync_scroll_region)
        self.content_canvas.bind("<Configure>", self._resize_scroll_content)
        self.content_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.scroll_content.bind("<MouseWheel>", self._on_mousewheel)

        self.question_label = ttk.Label(
            self.scroll_content,
            textvariable=self.question_text_var,
            style="Question.TLabel",
            justify=tk.LEFT,
            wraplength=560,
        )
        self.question_label.pack(fill=tk.X, pady=(0, 18))
        self.question_label.bind("<MouseWheel>", self._on_mousewheel)

        self.options_frame = tk.Frame(self.scroll_content, bg="#ffffff")
        self.options_frame.pack(fill=tk.BOTH, expand=True)
        self.options_frame.bind("<MouseWheel>", self._on_mousewheel)

        self.note_frame = tk.Frame(self.scroll_content, bg="#ffffff")
        self.note_header = ttk.Frame(self.note_frame, style="Panel.TFrame")
        self.note_header.pack(fill=tk.X)
        ttk.Label(self.note_header, text="笔记", style="Meta.TLabel").pack(side=tk.LEFT)
        self.note_status_label = ttk.Label(
            self.note_header,
            textvariable=self.note_status_var,
            style="Meta.TLabel",
            anchor=tk.E,
            justify=tk.RIGHT,
        )
        self.note_status_label.pack(side=tk.RIGHT)
        self.note_text = tk.Text(
            self.note_frame,
            height=6,
            wrap=tk.WORD,
            bg="#f8fafc",
            fg="#111827",
            insertbackground="#111827",
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=6,
            font=("Microsoft YaHei UI", 12, "bold"),
            undo=True,
        )
        self.note_text.pack(fill=tk.X, pady=(6, 0))
        self.note_text.bind("<KeyRelease>", self._schedule_note_save)
        self.note_text.bind("<FocusOut>", self._save_current_note)
        self.note_text.bind("<MouseWheel>", self._on_mousewheel)

        self.bottom_frame = ttk.Frame(self.question_panel, style="Panel.TFrame")
        self.bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        self.bottom_frame.columnconfigure(0, weight=1)
        self.bottom_frame.columnconfigure(1, weight=0)
        self.feedback_label = ttk.Label(
            self.bottom_frame,
            textvariable=self.feedback_var,
            style="Feedback.TLabel",
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=480,
        )
        self.feedback_label.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.submit_button = ttk.Button(
            self.bottom_frame,
            text="提交",
            width=10,
            style="Accent.TButton",
            command=self._primary_action,
        )
        self.submit_button.grid(row=0, column=1, sticky="e")

        self.side_panel = ttk.Frame(body, padding=18, style="Panel.TFrame", width=250)
        self.side_panel.grid(row=0, column=1, sticky="ns")
        self.side_panel.grid_propagate(False)

        self.progress_bar = ttk.Progressbar(
            self.side_panel,
            mode="determinate",
            maximum=1,
            value=0,
            style="Horizontal.TProgressbar",
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 16))

        order_settings = ttk.Frame(self.side_panel, style="Panel.TFrame")
        order_settings.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(order_settings, text="刷题顺序", style="Meta.TLabel").pack(anchor=tk.W)
        self.order_mode_combo = ttk.Combobox(
            order_settings,
            textvariable=self.order_mode_var,
            values=tuple(ORDER_MODE_VALUES),
            state="readonly",
            width=18,
        )
        self.order_mode_combo.pack(fill=tk.X, pady=(4, 0))
        self.order_mode_combo.bind("<<ComboboxSelected>>", self._on_practice_setting_changed)

        type_settings = ttk.Frame(self.side_panel, style="Panel.TFrame")
        type_settings.pack(fill=tk.X, pady=(0, 14))
        ttk.Label(type_settings, text="题型范围", style="Meta.TLabel").pack(anchor=tk.W)
        self.type_filter_combo = ttk.Combobox(
            type_settings,
            textvariable=self.type_filter_var,
            values=tuple(TYPE_FILTER_VALUES),
            state="readonly",
            width=18,
        )
        self.type_filter_combo.pack(fill=tk.X, pady=(4, 0))
        self.type_filter_combo.bind("<<ComboboxSelected>>", self._on_practice_setting_changed)

        self._add_stat("题库", self.file_var)
        self._add_stat("工作表", self.sheet_var)
        self._add_stat("总题数", self.total_var)
        self._add_stat("练习模式", self.mode_var)
        self._add_stat("错题数", self.wrong_book_count_var)
        self._add_stat("已答", self.answered_var)
        self._add_stat("正确", self.correct_var)
        self._add_stat("正确率", self.rate_var)

        settings = ttk.Frame(self.side_panel, style="Panel.TFrame")
        settings.pack(fill=tk.X, pady=(12, 4))
        ttk.Label(settings, text="连续答对移除", style="Meta.TLabel").pack(anchor=tk.W)
        controls = ttk.Frame(settings, style="Panel.TFrame")
        controls.pack(fill=tk.X, pady=(4, 0))
        self.remove_after_spinbox = tk.Spinbox(
            controls,
            from_=1,
            to=10,
            width=5,
            textvariable=self.remove_after_var,
            command=self._set_remove_after,
            justify=tk.CENTER,
            font=("Microsoft YaHei UI", 10),
        )
        self.remove_after_spinbox.pack(side=tk.LEFT)
        ttk.Label(controls, text="次", style="Panel.TLabel").pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(self.side_panel, text="清空错题", command=self._clear_wrong_book).pack(fill=tk.X, pady=(8, 0))

        status = ttk.Label(root, textvariable=self.status_var, style="TLabel", anchor=tk.W)
        status.pack(fill=tk.X)

    def _add_stat(self, label: str, variable: tk.StringVar) -> None:
        row = ttk.Frame(self.side_panel, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=7)
        ttk.Label(row, text=label, style="Meta.TLabel").pack(anchor=tk.W)
        ttk.Label(row, textvariable=variable, style="Panel.TLabel", wraplength=190).pack(anchor=tk.W, pady=(2, 0))

    def _bind_events(self) -> None:
        self.bind("<Return>", self._handle_enter)
        self.question_panel.bind("<Configure>", self._update_wrap_lengths)
        self.remove_after_spinbox.bind("<FocusOut>", lambda _event: self._set_remove_after())
        self.remove_after_spinbox.bind("<Return>", lambda _event: self._set_remove_after())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_initial_bank(self) -> None:
        saved_path = self._read_saved_bank_path()
        if saved_path:
            loaded = self._load_bank(saved_path, quiet=True, startup=True, show_error=False)
            if loaded:
                return

            self._clear_saved_bank_path()
            default_path = self._first_local_bank_path()
            if default_path and self._load_bank(default_path, quiet=True, show_error=False):
                self.status_var.set("上次题库路径失效，已改用默认题库。")
                if not _looks_like_pyinstaller_temp_path(saved_path):
                    messagebox.showwarning(
                        "自动导入失败",
                        f"无法导入上次题库：\n{saved_path}\n\n已改用默认题库。",
                    )
                return

            messagebox.showerror(
                "自动导入失败",
                f"无法导入上次题库：\n{saved_path}\n\n也没有找到可用的默认题库，请重新导入题库。",
            )
            self.status_var.set("上次题库导入失败，请重新导入题库。")
            return

        default_path = self._first_local_bank_path()
        if default_path:
            self._load_bank(default_path, quiet=True)
        else:
            self._show_empty_state("未导入题库")

    def _first_local_bank_path(self) -> Path | None:
        seen_dirs: set[Path] = set()
        for directory in (DATA_DIR, RESOURCE_DIR):
            if directory in seen_dirs or not directory.exists():
                continue
            seen_dirs.add(directory)
            excel_files = sorted(
                (
                    path
                    for path in directory.glob("*.xlsx")
                    if path.is_file() and not path.name.startswith("~$")
                ),
                key=lambda path: path.name.lower(),
            )
            if excel_files:
                return excel_files[0]
        return None

    def _read_saved_bank_path(self) -> Path | None:
        data = self._read_config()
        path = data.get("last_bank_path") if isinstance(data, dict) else None
        if not path:
            return None
        return Path(str(path))

    def _read_config(self) -> dict[str, object]:
        if not CONFIG_PATH.exists():
            return {}
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_config(self, data: dict[str, object]) -> bool:
        data["version"] = 2
        try:
            CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return False
        return True

    def _save_bank_path(self, path: Path) -> bool:
        if self._is_bundled_resource_path(path):
            return self._clear_saved_bank_path()

        try:
            saved_path = str(path.resolve())
        except OSError:
            saved_path = str(path)
        data = self._read_config()
        data["last_bank_path"] = saved_path
        return self._write_config(data)

    def _clear_saved_bank_path(self) -> bool:
        data = self._read_config()
        if "last_bank_path" not in data:
            return True
        data.pop("last_bank_path", None)
        return self._write_config(data)

    def _current_order_mode(self) -> str:
        return ORDER_MODE_VALUES.get(self.order_mode_var.get(), ORDER_RANDOM)

    def _current_type_filter(self) -> str:
        return TYPE_FILTER_VALUES.get(self.type_filter_var.get(), MODE_ALL)

    def _set_order_mode_value(self, value: str) -> None:
        self.order_mode_var.set(ORDER_MODE_LABELS.get(value, ORDER_MODE_LABELS[ORDER_RANDOM]))

    def _set_type_filter_value(self, value: str) -> None:
        self.type_filter_var.set(TYPE_FILTER_LABELS.get(value, TYPE_FILTER_LABELS[MODE_ALL]))

    def _set_app_title(self, title: str) -> None:
        self.app_title_var.set(title)
        self.title(title)

    def _set_question_type_title(self, question: Question) -> None:
        self._set_app_title(f"{question_type_name(question)}刷题")

    def _set_default_title(self) -> None:
        self._set_app_title("刷题软件")

    def _is_bundled_resource_path(self, path: Path) -> bool:
        return getattr(sys, "frozen", False) and _is_path_inside(path, RESOURCE_DIR)

    def _bank_identity_for(self, path: Path) -> str:
        if self._is_bundled_resource_path(path):
            return f"{BUNDLED_BANK_PREFIX}{path.name}"
        try:
            return str(path.resolve())
        except OSError:
            return str(path)

    def _bank_identity_matches(self, saved_identity: str, current_identity: str) -> bool:
        if saved_identity == current_identity:
            return True
        if current_identity.startswith(BUNDLED_BANK_PREFIX):
            bundled_name = current_identity[len(BUNDLED_BANK_PREFIX) :]
            saved_path = Path(saved_identity)
            return saved_path.name == bundled_name and _looks_like_pyinstaller_temp_path(saved_path)
        return False

    def _filtered_questions(self, questions: list[Question]) -> list[Question]:
        question_type = self._current_type_filter()
        if question_type == MODE_ALL:
            return list(questions)
        return [question for question in questions if question.question_type == question_type]

    def _resolved_bank_path(self) -> str:
        if not self.bank:
            return ""
        return self._bank_identity_for(self.bank.path)

    def _save_practice_state(self, resume_index: int | None = None, completed: bool = False) -> bool:
        if not self.bank or not self.session.questions:
            return False

        current_index = self.session.current_index if resume_index is None else resume_index
        if self.session.questions:
            current_index = max(0, min(current_index, len(self.session.questions) - 1))

        data = self._read_config()
        data["practice_state"] = {
            "bank_path": self._resolved_bank_path(),
            "session_mode": self.session.mode,
            "order_mode": self.session.order_mode,
            "type_filter": self.session.type_filter,
            "question_keys": [question_key(question) for question in self.session.questions],
            "current_index": current_index,
            "correct_count": self.session.correct_count,
            "wrong_count": self.session.wrong_count,
            "completed": completed,
        }
        return self._write_config(data)

    def _restore_saved_session(self) -> bool:
        if not self.bank:
            return False

        state = self._read_config().get("practice_state")
        if not isinstance(state, dict) or state.get("completed"):
            return False
        saved_bank_identity = str(state.get("bank_path", ""))
        if not self._bank_identity_matches(saved_bank_identity, self._resolved_bank_path()):
            return False

        session_mode = str(state.get("session_mode", MODE_ALL))
        if session_mode not in {MODE_ALL, MODE_WRONG}:
            session_mode = MODE_ALL

        order_mode = str(state.get("order_mode", ORDER_RANDOM))
        if order_mode not in {ORDER_RANDOM, ORDER_SEQUENTIAL}:
            order_mode = ORDER_RANDOM

        type_filter = str(state.get("type_filter", MODE_ALL))
        if type_filter not in TYPE_FILTER_LABELS:
            type_filter = MODE_ALL

        self._set_order_mode_value(order_mode)
        self._set_type_filter_value(type_filter)

        candidates = self._filtered_questions(self.questions)
        if session_mode == MODE_WRONG:
            candidates = self.wrong_book.questions_from(candidates)

        lookup = {question_key(question): question for question in candidates}
        keys = state.get("question_keys", [])
        if not isinstance(keys, list):
            return False

        ordered_questions = [lookup[key] for key in keys if isinstance(key, str) and key in lookup]
        if not ordered_questions:
            return False

        self.session = QuizSession.restore(
            ordered_questions,
            mode=session_mode,
            order_mode=order_mode,
            type_filter=type_filter,
            current_index=_safe_int(state.get("current_index"), 0),
            correct_count=_safe_int(state.get("correct_count"), 0),
            wrong_count=_safe_int(state.get("wrong_count"), 0),
        )
        self.mode_var.set("错题练习" if session_mode == MODE_WRONG else "全部题目")
        self.status_var.set("已恢复上次刷题进度。")
        self._show_current_question()
        return True

    def _handle_enter(self, _event: tk.Event) -> None:
        if getattr(self, "note_text", None) is _event.widget:
            return
        if not self.questions:
            return
        self._primary_action()

    def _sync_scroll_region(self, _event: tk.Event | None = None) -> None:
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    def _resize_scroll_content(self, event: tk.Event) -> None:
        self.content_canvas.itemconfigure(self.scroll_window, width=event.width)
        self._update_wrap_lengths(event)

    def _on_mousewheel(self, event: tk.Event) -> str:
        if event.delta:
            self.content_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _schedule_note_save(self, _event: tk.Event | None = None) -> None:
        if not self.note_editor_visible or not self.session.answered:
            return
        self._cancel_pending_note_save()
        self.note_status_var.set("正在保存...")
        self.note_save_after_id = self.after(500, self._run_scheduled_note_save)

    def _run_scheduled_note_save(self) -> None:
        self.note_save_after_id = None
        self._save_current_note()

    def _cancel_pending_note_save(self) -> None:
        after_id = self.note_save_after_id
        self.note_save_after_id = None
        if after_id:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass

    def _save_current_note(self, _event: tk.Event | None = None) -> bool | None:
        self._cancel_pending_note_save()
        if not self.note_editor_visible or not self.session.answered:
            return None

        question = self.session.current_question
        if question is None:
            return None

        saved = self.notes.set_note(question, self._note_text_value())
        if saved:
            self.note_status_var.set("笔记已保存。")
        else:
            self.note_status_var.set("笔记保存失败。")
            self._show_note_save_warning()
        self._sync_scroll_region()
        return saved

    def _note_text_value(self) -> str:
        return self.note_text.get("1.0", "end-1c").strip()

    def _show_note_editor(self, question: Question) -> None:
        self._cancel_pending_note_save()
        self.note_text.delete("1.0", tk.END)
        note = self.notes.note_for(question)
        if note:
            self.note_text.insert("1.0", note)
        self.note_status_var.set("")
        if not self.note_frame.winfo_ismapped():
            self.note_frame.pack(fill=tk.X, pady=(18, 0))
        self.note_editor_visible = True
        self._sync_scroll_region()
        self.after(50, self._scroll_note_into_view)

    def _hide_note_editor(self, save: bool = True) -> None:
        if save:
            self._save_current_note()
        else:
            self._cancel_pending_note_save()
        self.note_editor_visible = False
        self.note_status_var.set("")
        self.note_text.delete("1.0", tk.END)
        self.note_frame.pack_forget()
        self._sync_scroll_region()

    def _scroll_note_into_view(self) -> None:
        if not self.note_editor_visible:
            return
        self.content_canvas.update_idletasks()
        self._sync_scroll_region()
        bbox = self.content_canvas.bbox("all")
        if not bbox:
            return

        content_height = max(1, bbox[3] - bbox[1])
        viewport_height = self.content_canvas.winfo_height()
        if content_height <= viewport_height:
            return

        target_y = max(0, self.note_frame.winfo_y() - 8)
        max_scroll = max(1, content_height - viewport_height)
        self.content_canvas.yview_moveto(min(1, target_y / max_scroll))

    def _show_note_save_warning(self) -> None:
        if not self.notes.last_save_ok and self.notes.last_error:
            self.status_var.set(f"笔记保存失败：{self.notes.last_error}")

    def _on_close(self) -> None:
        self._save_current_note()
        self.destroy()

    def _update_wrap_lengths(self, event: tk.Event) -> None:
        wrap_length = max(320, event.width - 24)
        self.question_label.configure(wraplength=wrap_length)
        for button in self.option_buttons.values():
            button.configure(wraplength=wrap_length - 28)
        feedback_width = max(220, event.width - self.submit_button.winfo_reqwidth() - 72)
        self.feedback_label.configure(wraplength=feedback_width)
        self.note_status_label.configure(wraplength=max(120, wrap_length // 2))

    def _choose_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择题库 Excel",
            initialdir=DATA_DIR if DATA_DIR.exists() else RESOURCE_DIR,
            filetypes=(("Excel 文件", "*.xlsx"), ("所有文件", "*.*")),
        )
        if filename:
            self._load_bank(Path(filename), quiet=False)

    def _load_bank(self, path: Path, quiet: bool, startup: bool = False, show_error: bool = True) -> bool:
        try:
            bank = read_question_bank(path)
        except QuestionImportError as exc:
            self._show_empty_state("题库导入失败")
            if not show_error:
                return False
            if startup:
                messagebox.showerror(
                    "自动导入失败",
                    f"无法导入上次题库：\n{path}\n\n{exc}\n\n请重新导入题库。",
                )
            else:
                messagebox.showerror("导入失败", str(exc))
            return False

        self.bank = bank
        self.questions = bank.questions
        saved_path = self._save_bank_path(bank.path)
        self.file_var.set(bank.path.name)
        self.sheet_var.set(bank.sheet_name)
        self.total_var.set(str(len(bank.questions)))
        self._refresh_wrong_book_count()
        if saved_path:
            import_status = f"已导入 {len(bank.questions)} 道题。"
        else:
            import_status = f"已导入 {len(bank.questions)} 道题，但上次题库路径保存失败。"
        restored = self._restore_saved_session()
        if restored:
            self.status_var.set(f"{import_status} 已恢复上次刷题进度。")
        else:
            self._restart_quiz()
            self.status_var.set(import_status)

        if bank.skipped_rows and not quiet:
            details = "\n".join(bank.skipped_rows[:5])
            more = "" if len(bank.skipped_rows) <= 5 else f"\n另有 {len(bank.skipped_rows) - 5} 行被跳过。"
            messagebox.showwarning("导入完成", f"导入 {len(bank.questions)} 道题。\n{details}{more}")
        elif not quiet:
            messagebox.showinfo("导入完成", f"已导入 {len(bank.questions)} 道题。")
        return True

    def _restart_quiz(self) -> None:
        if not self.questions:
            self._show_empty_state("未导入题库")
            return

        questions = self._filtered_questions(self.questions)
        if not questions:
            self.session = QuizSession.empty(MODE_ALL, self._current_type_filter())
            self.mode_var.set("全部题目")
            self._show_question_placeholder("当前题型没有可练习的题目。")
            self.status_var.set("当前题型没有可练习的题目。")
            return

        self._start_quiz(questions, MODE_ALL)

    def _start_wrong_quiz(self) -> None:
        if not self.questions:
            messagebox.showinfo("练习错题", "请先导入题库。")
            return

        wrong_questions = self.wrong_book.questions_from(self._filtered_questions(self.questions))
        if not wrong_questions:
            self._refresh_wrong_book_count()
            self.session = QuizSession.empty(MODE_WRONG, self._current_type_filter())
            self.mode_var.set("错题练习")
            self._show_question_placeholder("当前题库没有错题。")
            messagebox.showinfo("练习错题", "当前题库没有错题。")
            return

        self._start_quiz(wrong_questions, MODE_WRONG)

    def _start_quiz(self, questions: list[Question], mode: str) -> None:
        note_saved = self._save_current_note()
        order_mode = self._current_order_mode()
        type_filter = self._current_type_filter()
        self.session = QuizSession.start(questions, mode, order_mode, type_filter)
        self.mode_var.set("错题练习" if mode == MODE_WRONG else "全部题目")
        self.selected_answer.set("")
        order_text = ORDER_MODE_LABELS.get(order_mode, "随机刷题")
        self.status_var.set(f"{'错题' if mode == MODE_WRONG else '题目'}已按“{order_text}”开始。")
        self._show_current_question()
        self._save_practice_state()
        if note_saved is False:
            self._show_note_save_warning()

    def _on_practice_setting_changed(self, _event: tk.Event | None = None) -> None:
        if self.questions:
            if self.session.mode == MODE_WRONG:
                self._start_wrong_quiz()
            else:
                self._restart_quiz()

    def _show_current_question(self) -> None:
        question = self.session.current_question
        if question is None:
            self._show_question_placeholder("当前没有可练习的题目。")
            return

        self._set_question_type_title(question)
        self._hide_note_editor(save=False)
        self.selected_answer.set("")
        self.feedback_var.set("")
        self.feedback_label.configure(style="Feedback.TLabel")

        self.progress_var.set(f"第 {self.session.current_index + 1} / {self.session.total} 题")
        self.question_number_var.set(self._question_mark(question))
        self.question_text_var.set(question.stem)

        for child in self.options_frame.winfo_children():
            child.destroy()
        self.option_buttons.clear()
        self.multi_answer_vars.clear()

        wrap_length = max(320, self.content_canvas.winfo_width() - 24)
        for letter, text in question.options.items():
            if question.question_type == TYPE_MULTI:
                variable = tk.BooleanVar(value=False)
                self.multi_answer_vars[letter] = variable
                button = tk.Checkbutton(
                    self.options_frame,
                    text=f"{letter}. {text}",
                    variable=variable,
                    bg="#ffffff",
                    activebackground="#ffffff",
                    fg="#1f2937",
                    selectcolor="#e0f2fe",
                    anchor=tk.W,
                    justify=tk.LEFT,
                    wraplength=wrap_length,
                    font=("Microsoft YaHei UI", 11),
                    padx=8,
                    pady=8,
                    command=self._on_select_answer,
                )
            else:
                button = tk.Radiobutton(
                    self.options_frame,
                    text=f"{letter}. {text}",
                    value=letter,
                    variable=self.selected_answer,
                    bg="#ffffff",
                    activebackground="#ffffff",
                    fg="#1f2937",
                    selectcolor="#e0f2fe",
                    anchor=tk.W,
                    justify=tk.LEFT,
                    wraplength=wrap_length,
                    font=("Microsoft YaHei UI", 11),
                    padx=8,
                    pady=8,
                    command=self._on_select_answer,
                )
            button.bind("<MouseWheel>", self._on_mousewheel)
            button.pack(fill=tk.X, anchor=tk.W, pady=3)
            self.option_buttons[letter] = button

        self.submit_button.configure(text="提交", command=self._primary_action, state=tk.DISABLED)
        self.content_canvas.yview_moveto(0)
        self._sync_scroll_region()
        self._update_stats()

    def _show_question_placeholder(self, text: str) -> None:
        self._set_default_title()
        self._hide_note_editor()
        self.progress_var.set("-")
        self.question_number_var.set("")
        self.question_text_var.set(text)
        self.feedback_var.set("")
        self.feedback_label.configure(style="Feedback.TLabel")
        self.selected_answer.set("")
        for child in self.options_frame.winfo_children():
            child.destroy()
        self.option_buttons.clear()
        self.multi_answer_vars.clear()
        self.submit_button.configure(text="提交", command=self._primary_action, state=tk.DISABLED)
        self.content_canvas.yview_moveto(0)
        self._sync_scroll_region()
        self._update_stats()

    def _question_mark(self, question: Question) -> str:
        base = f"原表第 {question.source_row} 行" if not question.number else f"题号 {question.number}"
        label = f"{question_type_name(question)} | {base}"
        record = self.wrong_book.record_for(question)
        if record:
            label = f"{label} | 错题 {record.correct_streak}/{self.wrong_book.remove_after}"
        return label

    def _update_current_question_mark(self) -> None:
        question = self.session.current_question
        if question:
            self.question_number_var.set(self._question_mark(question))

    def _on_select_answer(self) -> None:
        if not self.session.answered:
            state = tk.NORMAL if self._selected_answer() else tk.DISABLED
            self.submit_button.configure(state=state)

    def _selected_answer(self) -> tuple[str, ...]:
        question = self.session.current_question
        if question is None:
            return ()
        if question.question_type == TYPE_MULTI:
            return tuple(
                letter
                for letter in question.options
                if self.multi_answer_vars.get(letter) and self.multi_answer_vars[letter].get()
            )
        selected = self.selected_answer.get()
        return (selected,) if selected else ()

    def _selected_answer_text(self, selected: tuple[str, ...]) -> str:
        return ";".join(selected)

    def _primary_action(self) -> None:
        if self.session.current_question is None:
            return
        if self.session.answered:
            self._next_question()
        else:
            self._submit_answer()

    def _submit_answer(self) -> None:
        if not self.questions or self.session.answered:
            return

        selected = self._selected_answer()
        if not selected:
            self.feedback_var.set("请先选择选项。")
            self.feedback_label.configure(style="Danger.TLabel")
            return

        question = self.session.current_question
        if question is None:
            return

        is_correct = selected == question.answer
        self.session.record_answer(is_correct)
        if is_correct:
            streak, removed = self.wrong_book.mark_correct(question)
            if removed:
                self.feedback_var.set("答对了，已从错题本移除。")
            elif streak:
                self.feedback_var.set(f"答对了，错题本连续答对 {streak}/{self.wrong_book.remove_after} 次。")
            else:
                self.feedback_var.set("答对了。")
            self.feedback_label.configure(style="Feedback.TLabel")
        else:
            self.wrong_book.mark_wrong(question, self._selected_answer_text(selected))
            self.feedback_var.set(
                f"答错了，正确答案：{format_answer(question)}。"
                f" 已加入错题本，连续答对 {self.wrong_book.remove_after} 次后移除。"
            )
            self.feedback_label.configure(style="Danger.TLabel")
        self._refresh_wrong_book_count()
        self._update_current_question_mark()

        for letter, button in self.option_buttons.items():
            color = "#166534" if letter in question.answer else "#b91c1c" if letter in selected else "#64748b"
            button.configure(state=tk.DISABLED, disabledforeground=color)

        self._show_note_editor(question)
        if self.session.has_next:
            self.submit_button.configure(text="下一题", command=self._primary_action, state=tk.NORMAL)
        else:
            self.submit_button.configure(text="完成", command=self._primary_action, state=tk.DISABLED)
            self.status_var.set(self._summary_text())
        self._update_stats()
        next_index = self.session.current_index + 1 if self.session.has_next else self.session.current_index
        self._save_practice_state(resume_index=next_index, completed=not self.session.has_next)
        self._show_wrong_book_save_warning()

    def _next_question(self) -> None:
        if not self.questions:
            return
        note_saved = self._save_current_note()
        if not self.session.next_question():
            return
        if note_saved is False:
            self._show_note_save_warning()
        else:
            self.status_var.set("继续。")
        self._show_current_question()
        self._save_practice_state()

    def _set_remove_after(self) -> None:
        try:
            value = int(self.remove_after_var.get())
        except (tk.TclError, ValueError):
            value = self.wrong_book.remove_after

        saved = self.wrong_book.set_remove_after(value)
        self.remove_after_var.set(self.wrong_book.remove_after)
        if saved:
            self.status_var.set(f"错题连续答对 {self.wrong_book.remove_after} 次后自动移除。")
        else:
            self._show_wrong_book_save_warning()
        self._update_current_question_mark()

    def _refresh_wrong_book_count(self) -> None:
        count = self.wrong_book.count_for(self._filtered_questions(self.questions)) if self.questions else 0
        self.wrong_book_count_var.set(str(count))

    def _show_wrong_book_save_warning(self) -> None:
        if not self.wrong_book.last_save_ok and self.wrong_book.last_error:
            self.status_var.set(f"错题记录保存失败：{self.wrong_book.last_error}")

    def _clear_wrong_book(self) -> None:
        if not self.questions:
            messagebox.showinfo("清空错题", "请先导入题库。")
            return

        count = self.wrong_book.count_for(self.questions)
        if count == 0:
            messagebox.showinfo("清空错题", "当前题库没有错题。")
            return

        confirmed = messagebox.askyesno("清空错题", f"确定清空当前题库的 {count} 道错题吗？")
        if not confirmed:
            return

        removed = self.wrong_book.clear_for(self.questions)
        self._refresh_wrong_book_count()
        self.status_var.set(f"已清空 {removed} 道错题。")
        self._show_wrong_book_save_warning()
        if self.session.mode == MODE_WRONG:
            self.session = QuizSession.empty(MODE_WRONG)
            self.mode_var.set("错题练习")
            self._show_question_placeholder("当前题库没有错题。")
        else:
            self._update_current_question_mark()

    def _update_stats(self) -> None:
        total = self.session.total
        answered = self.session.answered_count
        rate = 0 if answered == 0 else self.session.correct_count / answered
        self.answered_var.set(str(answered))
        self.correct_var.set(str(self.session.correct_count))
        self.rate_var.set(f"{rate:.0%}")
        self.progress_bar.configure(maximum=max(total, 1), value=answered)

    def _summary_text(self) -> str:
        answered = self.session.answered_count
        rate = 0 if answered == 0 else self.session.correct_count / answered
        return f"本轮完成：{answered} 题，正确 {self.session.correct_count} 题，正确率 {rate:.0%}。"

    def _show_empty_state(self, status: str) -> None:
        self._set_default_title()
        self._hide_note_editor()
        self.bank = None
        self.questions = []
        self.session = QuizSession.empty(MODE_ALL)
        self.progress_var.set("-")
        self.question_number_var.set("")
        self.question_text_var.set("请导入 Excel 题库。")
        self.feedback_var.set("")
        self.file_var.set("未导入")
        self.sheet_var.set("-")
        self.total_var.set("0")
        self.mode_var.set("全部题目")
        self.wrong_book_count_var.set("0")
        self.answered_var.set("0")
        self.correct_var.set("0")
        self.rate_var.set("0%")
        self.status_var.set(status)
        self.progress_bar.configure(maximum=1, value=0)

        for child in self.options_frame.winfo_children():
            child.destroy()
        self.option_buttons.clear()
        self.multi_answer_vars.clear()
        self.submit_button.configure(text="提交", command=self._primary_action, state=tk.DISABLED)


def _is_path_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except (OSError, ValueError):
        return False
    return True


def _looks_like_pyinstaller_temp_path(path: Path) -> bool:
    return any(part.startswith("_MEI") for part in path.parts)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def main() -> None:
    app = QuizApp()
    app.mainloop()


if __name__ == "__main__":
    main()
