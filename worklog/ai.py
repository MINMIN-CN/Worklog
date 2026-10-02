"""OpenAI 兼容接口客户端（支持视觉与文本），以及宽松 JSON 解析。"""

from __future__ import annotations

import json
import re
import threading
import time

import httpx

from . import i18n
from .net import default_verify


class AIError(RuntimeError):
    pass


def _friendly_http_error(status: int, body: str) -> str:
    snippet = (body or "").strip().replace("\n", " ")[:200]
    if status == 401:
        return i18n.tr("API Key 无效或未授权（HTTP 401）")
    if status == 403:
        return i18n.tr("无权访问该模型（HTTP 403）")
    if status == 404:
        return i18n.tr("接口地址或模型名不存在（HTTP 404）")
    if status == 429:
        return i18n.tr("请求过于频繁或额度不足（HTTP 429）")
    if status >= 500:
        return i18n.tr("模型服务异常（HTTP {status}）").format(status=status)
    return i18n.tr("接口返回错误（HTTP {status}）：{snippet}").format(
        status=status, snippet=snippet
    )


class AIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 120,
        json_mode: bool = False,
        thinking: str = "auto",
        reasoning_effort: str = "auto",
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout = float(timeout or 120)
        self.json_mode = bool(json_mode)
        self.thinking = (thinking or "auto").lower()
        self.reasoning_effort = (reasoning_effort or "auto").lower()
        self._client = httpx.Client(
            timeout=self.timeout,
            verify=default_verify(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def chat(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        json_mode: bool | None = None,
    ) -> str:
        if not self.base_url:
            raise AIError(i18n.tr("未配置 API 地址"))
        if not self.api_key:
            raise AIError(i18n.tr("未配置 API Key"))

        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # DeepSeek 等支持思考模式的模型：默认不指定，避免未知字段导致 400
        if self.thinking in ("enabled", "disabled"):
            payload["thinking"] = {"type": self.thinking}
        if self.reasoning_effort in ("low", "high", "max"):
            payload["reasoning_effort"] = self.reasoning_effort
        use_json = self.json_mode if json_mode is None else bool(json_mode)
        if use_json:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.post(url, json=payload)
            except httpx.TransportError as exc:
                last_error = AIError(
                    i18n.tr("无法连接模型接口：{message}").format(message=exc)
                )
                if attempt == 0:
                    time.sleep(2)
                    continue
                raise last_error

            if response.status_code >= 400:
                message = _friendly_http_error(response.status_code, response.text)
                if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    last_error = AIError(message)
                    time.sleep(2)
                    continue
                raise AIError(message)

            try:
                data = response.json()
                choice = (data.get("choices") or [{}])[0]
                message_data = choice.get("message") or {}
                content = message_data.get("content")
                finish_reason = choice.get("finish_reason")
                reasoning = message_data.get("reasoning_content") or ""
            except Exception as exc:
                raise AIError(
                    i18n.tr("响应格式异常：{message}").format(message=str(exc)[:120])
                ) from exc

            if isinstance(content, list):
                parts: list[str] = []
                for part in content:
                    if isinstance(part, dict):
                        parts.append(str(part.get("text") or part.get("content") or ""))
                    else:
                        parts.append(str(part))
                content = "".join(parts)

            text = (content or "").strip()
            if not text:
                # 输出预算被思考占用导致空内容时，自动翻倍重试一次
                if finish_reason == "length" and attempt == 0:
                    current = int(payload.get("max_tokens") or 1024)
                    payload["max_tokens"] = min(current * 2, 16000)
                    last_error = AIError(
                        i18n.tr("模型输出被截断（可能把预算用在思考上），已自动重试…")
                    )
                    continue
                if reasoning:
                    raise AIError(
                        i18n.tr(
                            "模型把输出预算都用在思考上了（未返回内容）。"
                            "请在设置 → 高级设置中关闭「思考模式」后重试。"
                        )
                    )
                raise AIError(i18n.tr("模型返回了空内容，请重试或在设置中调整模型。"))
            return text

        raise last_error or AIError(i18n.tr("请求失败"))


_client_cache: dict[tuple, AIClient] = {}
_client_lock = threading.Lock()


def make_client(cfg) -> AIClient:
    """按配置构造（并复用）客户端。"""
    base_url = cfg.get("api", "base_url", default="") or ""
    api_key = cfg.get("api", "api_key", default="") or ""
    timeout = cfg.get("api", "timeout", default=120) or 120
    json_mode = bool(cfg.get("api", "use_json_mode", default=False))
    provider = (cfg.get("api", "provider", default="") or "").lower()
    thinking = (cfg.get("api", "thinking", default="auto") or "auto").lower()
    if thinking == "auto" and provider == "deepseek":
        # DeepSeek 思考模式默认开启，容易耗尽输出预算导致空内容；本应用默认关闭
        thinking = "disabled"
    effort = (cfg.get("api", "reasoning_effort", default="auto") or "auto").lower()
    key = (base_url, api_key, float(timeout), json_mode, thinking, effort)
    with _client_lock:
        client = _client_cache.get(key)
        if client is None:
            client = AIClient(
                base_url, api_key, timeout, json_mode, thinking, effort
            )
            # 配置变更较少，缓存保留最近几组即可
            if len(_client_cache) > 4:
                _client_cache.clear()
            _client_cache[key] = client
        return client


def has_api_key(cfg) -> bool:
    return bool((cfg.get("api", "api_key", default="") or "").strip())


def parse_json_loose(text: str) -> dict | None:
    """从模型输出中尽力提取 JSON 对象。"""
    if not text:
        return None
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", cleaned, re.S)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except Exception:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(cleaned[start : end + 1])
            return value if isinstance(value, dict) else None
        except Exception:
            return None
    return None


def parse_json_list_loose(text: str) -> list | None:
    """从模型输出中尽力提取 JSON 数组。"""
    if not text:
        return None
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", cleaned, re.S)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        value = json.loads(cleaned)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in ("todos", "items", "list", "data"):
                if isinstance(value.get(key), list):
                    return value[key]
    except Exception:
        pass
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start != -1 and end > start:
        try:
            value = json.loads(cleaned[start : end + 1])
            return value if isinstance(value, list) else None
        except Exception:
            return None
    return None
