# Excel 题库刷题工具 / Excel Question Bank Practice

[中文](#chinese) | [English](#english)

<a id="chinese"></a>

## 中文

`quiz_app.py` 是一个 Tkinter 桌面刷题软件，可以导入 `.xlsx` 题库，按题型练习，记录错题，并为题目保存笔记。它不依赖 pandas 或 openpyxl，而是直接读取 xlsx 内部 XML。

### 功能

- 导入 Excel 题库。
- 支持单选题、多选题、判断题。
- 支持随机刷题和顺序刷题。
- 支持按题型筛选练习。
- 答题后显示正确答案和反馈。
- 自动记录错题，错题连续答对指定次数后自动移除。
- 支持单独练习错题。
- 支持清空当前题库对应的错题记录。
- 支持题目笔记，答题后显示并自动保存。
- 自动保存上次题库路径和练习进度。

### 文件说明

| 文件 | 说明 |
| --- | --- |
| `quiz_app.py` | 主程序，包含 Tkinter 界面和练习流程 |
| `question_bank.py` | 读取 `.xlsx` 题库并转换为题目对象 |
| `quiz_session.py` | 当前练习会话、顺序和统计状态 |
| `wrong_book.py` | 错题记录、错题哈希键、连续答对移除逻辑 |
| `notes.py` | 题目笔记读写逻辑 |
| `practice.xlsx` | 用户本地题库，已忽略，不随源码分发 |
| `wrong_book.json` | 错题本数据 |
| `notes.json` | 题目笔记数据 |
| `app_config.json` | 上次题库路径、练习进度和配置 |

### 运行

在仓库根目录执行：

```powershell
python quiz_app.py
```

### 题库格式

题库文件需要是 `.xlsx`。程序会在工作表中寻找题库表头，核心字段包括：

- 题干、题目或问题。
- 正确答案或答案。
- 序号、编号或题号，非必需。
- 选择题需要选项列，例如 `A`、`B`、`C`、`D` 或类似“选项A”的列名。

题型识别方式：

- 工作表名称包含“单”时倾向识别为单选题。
- 工作表名称包含“多”时倾向识别为多选题。
- 工作表名称包含“判断”时识别为判断题。
- 如果无法从表名判断，程序会根据是否存在选项列推断。

答案填写建议：

- 单选题答案填写 `A`、`B`、`C` 等。
- 多选题可填写多个字母，例如 `ABCD`、`A,B,C`。
- 判断题可填写对、错、正确、错误、true、false 等可识别形式。

### 数据保存

- 错题记录保存在 `wrong_book.json`。
- 笔记保存在 `notes.json`。
- 上次打开的题库路径和当前练习状态保存在 `app_config.json`。

这些文件都在本目录内，迁移或备份刷题数据时可以一起复制。它们包含个人学习记录、笔记和文件路径，已从版本控制中排除。新克隆的仓库首次运行时选择自己的题库，程序会自动创建所需的本地数据文件。

<a id="english"></a>

## English

`quiz_app.py` is a Tkinter desktop application for practicing questions imported from `.xlsx` workbooks. It tracks incorrect answers, progress, and question notes. It reads XML directly from the workbook archive and does not require pandas or openpyxl. The application interface is in Chinese.

### Features

- Import an Excel question bank.
- Practice single-choice, multiple-choice, and true/false questions.
- Practice in order or randomly, and filter by question type.
- Show the correct answer and feedback after submission.
- Track incorrect answers and remove them after the required number of consecutive correct answers.
- Practice only the incorrect-answer collection, or clear it for the current question bank.
- Save notes for individual questions automatically.
- Remember the last question-bank path and practice progress.

### Files

| File | Purpose |
| --- | --- |
| `quiz_app.py` | Tkinter interface and practice workflow |
| `question_bank.py` | Read `.xlsx` workbooks and create question objects |
| `quiz_session.py` | Session state, question order, and statistics |
| `wrong_book.py` | Incorrect-answer records, question hashes, and consecutive-correct tracking |
| `notes.py` | Read and write question notes |
| `practice.xlsx` | User-owned local question bank; ignored by Git |
| `wrong_book.json` | Local incorrect-answer records |
| `notes.json` | Local question notes |
| `app_config.json` | Last workbook path, progress, and settings |

### Run

From the repository root:

```powershell
python quiz_app.py
```

The application uses Python's standard library, including Tkinter.

### Question-bank format

Use an `.xlsx` file. The importer searches for headings such as:

- `题干`, `题目`, or `问题`: question text.
- `正确答案` or `答案`: correct answer.
- `序号`, `编号`, or `题号`: optional question number.
- Choice columns such as `A`, `B`, `C`, `D`, or `选项A`.

Worksheet names containing `单` suggest single-choice questions, names containing `多` suggest multiple-choice questions, and names containing `判断` suggest true/false questions. If the name does not identify a type, the importer infers it from options and answer structure.

Recommended answer formats:

- Single choice: `A`, `B`, `C`, and so on.
- Multiple choice: `ABCD`, `A,B,C`, or a similar multi-letter form.
- True/false: `对`, `错`, `正确`, `错误`, `true`, `false`, or another supported form.

### Local data and privacy

`wrong_book.json`, `notes.json`, and `app_config.json` are stored beside the application. They contain personal practice records, notes, and file paths and are excluded from version control. Local Excel workbooks are excluded as well.

Copy these files together when migrating or backing up your practice data. A fresh clone asks you to select your own workbook and creates the local data files as needed.
