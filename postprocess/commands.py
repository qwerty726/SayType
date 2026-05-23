"""Voice command parsing.

If the entire utterance matches a command phrase, return the corresponding
action so we can perform it instead of typing the literal characters. This is
what makes the product a real input method rather than a transcription tool.

Actions returned:
- ("text", str)   : insert literal text (e.g. punctuation replacement)
- ("key", str)    : press a keyboard shortcut (pyautogui hotkey syntax)
- ("none", "")    : no command; caller should insert the original transcription
"""
from __future__ import annotations

import re
from typing import Tuple

# (regex, action_kind, payload)
_COMMANDS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^[,，。\.\s]*(换行|回车|新起一行)[,，。\.\s]*$"), "key", "enter"),
    (re.compile(r"^[,，。\.\s]*(空格)[,，。\.\s]*$"), "key", "space"),
    (re.compile(r"^[,，。\.\s]*(制表符|tab键?)[,，。\.\s]*$"), "key", "tab"),
    (re.compile(r"^[,，。\.\s]*(删除|退格|删一个字)[,，。\.\s]*$"), "key", "backspace"),
    (re.compile(r"^[,，。\.\s]*(全选)[,，。\.\s]*$"), "key", "ctrl+a"),
    (re.compile(r"^[,，。\.\s]*(复制)[,，。\.\s]*$"), "key", "ctrl+c"),
    (re.compile(r"^[,，。\.\s]*(粘贴)[,，。\.\s]*$"), "key", "ctrl+v"),
    (re.compile(r"^[,，。\.\s]*(撤销|撤回)[,，。\.\s]*$"), "key", "ctrl+z"),
    (re.compile(r"^[,，。\.\s]*(保存)[,，。\.\s]*$"), "key", "ctrl+s"),
    (re.compile(r"^[,，。\.\s]*(句号)[,，。\.\s]*$"), "text", "。"),
    (re.compile(r"^[,，。\.\s]*(逗号)[,，。\.\s]*$"), "text", "，"),
    (re.compile(r"^[,，。\.\s]*(问号)[,，。\.\s]*$"), "text", "？"),
    (re.compile(r"^[,，。\.\s]*(感叹号|叹号)[,，。\.\s]*$"), "text", "！"),
    (re.compile(r"^[,，。\.\s]*(冒号)[,，。\.\s]*$"), "text", "："),
    (re.compile(r"^[,，。\.\s]*(分号)[,，。\.\s]*$"), "text", "；"),
    (re.compile(r"^[,，。\.\s]*(顿号)[,，。\.\s]*$"), "text", "、"),
]


def parse_command(text: str) -> Tuple[str, str]:
    if not text:
        return ("none", "")
    stripped = text.strip()
    for pattern, kind, payload in _COMMANDS:
        if pattern.match(stripped):
            return (kind, payload)
    return ("none", "")
