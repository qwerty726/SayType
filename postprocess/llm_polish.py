"""Optional LLM-based polish: spoken -> written, fix obvious ASR mistakes.

Off by default. Enabled in settings with an API key. Adds ~1s latency, so we
keep it as a power-user toggle to honor the "cost controllable" design goal.
"""
from __future__ import annotations

import json

import requests


SYSTEM_PROMPT = (
    "你是一个语音输入法的文本润色助手。任务：将口语化的语音转写文本整理为通顺、"
    "标点准确的书面表达。规则：1) 仅修正明显的语病、口头禅、重复词；2) 保留用户"
    "原意，不要扩写或概括；3) 不要回答用户、不要添加任何解释；4) 直接输出润色后"
    "的文本，不要使用引号或前后缀。"
)


def polish(text: str, api_key: str, base_url: str, model: str, timeout: float = 8.0) -> str:
    if not text or not api_key:
        return text
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        polished = data["choices"][0]["message"]["content"].strip()
        return polished or text
    except Exception:
        # On any failure, fall back to the raw transcription - never lose user input.
        return text
