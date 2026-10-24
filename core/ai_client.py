"""模型调用封装。

三条设计原则，写进技术文档就是"架构决策"：

1. 只认三个环境变量（API_KEY / BASE_URL / MODEL），换供应商不改代码。
2. 密钥永不进日志、永不进页面明文，展示时一律脱敏。
3. 配置缺失或调用失败，返回结构化结果而不是抛裸异常——
   让上层页面能显示"为什么不能用"，而不是白屏。

本地读 .env，云端读 Streamlit Secrets，两条路都支持。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

_REQUIRED = "OPENAI_API_KEY"
_OPTIONAL = ("OPENAI_BASE_URL", "OPENAI_MODEL")


@dataclass(frozen=True)
class AIConfig:
    api_key: str
    base_url: str
    model: str
    source: str  # 从哪读到的，便于排查

    @property
    def state(self) -> str:
        """missing / placeholder / invalid / ok。

        分成四态而不是一个布尔，是因为「没读到」「读到了但还是模板原文」
        「格式不像密钥」对应的处理办法完全不同，混成一句话会让人白折腾。
        """
        k = self.api_key.strip()
        if not k:
            return "missing"
        if "在这里" in k or not k.startswith("sk-"):
            return "placeholder"
        if len(k) < 20:
            return "invalid"
        return "ok"

    @property
    def configured(self) -> bool:
        """密钥形态是否像真的。只做格式判断，不验证有效性。"""
        return self.state == "ok"

    @property
    def masked_key(self) -> str:
        k = self.api_key.strip()
        if not k:
            return "（未设置）"
        if len(k) <= 8:
            return "****"
        return f"{k[:4]}****{k[-4:]} · 共 {len(k)} 位"


def _from_streamlit_secrets() -> dict[str, str]:
    """Streamlit Cloud 上密钥存在 Secrets 里，不在环境变量。"""
    try:
        import streamlit as st

        raw = st.secrets  # 无 secrets.toml 时这里会抛异常
        out: dict[str, str] = {}
        for key in (_REQUIRED, *_OPTIONAL):
            try:
                val = raw[key]
            except Exception:
                continue
            if val:
                out[key] = str(val)
        return out
    except Exception:
        return {}


def _from_dotenv() -> dict[str, str]:
    """本地开发从 .env 读。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return {}
    load_dotenv(override=False)
    out: dict[str, str] = {}
    for key in (_REQUIRED, *_OPTIONAL):
        val = os.environ.get(key)
        if val:
            out[key] = val
    return out


def load_config() -> AIConfig:
    """优先级：Streamlit Secrets > .env / 环境变量。"""
    secrets = _from_streamlit_secrets()
    if secrets.get(_REQUIRED):
        source = "Streamlit Secrets"
        data = secrets
    else:
        data = _from_dotenv()
        source = ".env / 环境变量" if data.get(_REQUIRED) else "未找到"

    return AIConfig(
        api_key=data.get(_REQUIRED, ""),
        base_url=(data.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
        model=data.get("OPENAI_MODEL") or DEFAULT_MODEL,
        source=source,
    )


def ping(config: AIConfig, timeout: float = 40.0) -> tuple[bool, str]:
    """最小成本连通性测试：发一句"回复：可用"，限制 8 token。

    返回 (是否成功, 给人看的一句话)。不抛异常。
    """
    if not config.configured:
        return False, "密钥未配置或格式不对，无法测试。"

    try:
        from openai import OpenAI
    except ImportError:
        return False, "缺少 openai 依赖，请先 pip install openai。"

    try:
        client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=timeout)
        resp = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": "回复：可用"}],
            max_tokens=8,
            temperature=0,
        )
        reply = (resp.choices[0].message.content or "").strip()
        return True, f"模型已回话：{reply[:40]}"
    except Exception as exc:  # noqa: BLE001 - 上层需要展示原因，不该白屏
        return False, _explain(exc, config.model)


def _explain(exc: Exception, model: str) -> str:
    """把 SDK 的英文异常翻译成能照着处理的一句话。

    这层看着啰嗦，实际决定用户会不会在同一类错误上反复折腾：
    「401」和「402」到了界面上都是"调用失败"，但处理办法完全不同。
    """
    msg = str(exc)
    low = msg.lower()
    if "401" in msg or "Authentication" in msg or "invalid_api_key" in msg:
        return "密钥无效或已过期（401）。"
    if "402" in msg or "Insufficient Balance" in msg or "余额" in msg:
        return "账户余额不足（402），需要充值。"
    if "404" in msg or "model_not_found" in msg:
        return f"模型 {model} 不存在，检查 OPENAI_MODEL 拼写。"
    if "429" in msg or "rate limit" in low:
        return "触发限流（429），等几十秒再试。"
    if "timeout" in low or "timed out" in low:
        return "请求超时，检查网络或 BASE_URL。"
    return f"调用失败：{msg[:160]}"


def chat(
    config: AIConfig,
    system: str,
    user: str,
    max_tokens: int = 900,
    temperature: float = 0.3,
    timeout: float = 60.0,
) -> tuple[bool, str]:
    """通用对话入口，返回 (是否成功, 文本或错误说明)。

    业务层只看第一个返回值就够了，不必自己写 try/except ——
    失败时第二个值已经是可直接显示给用户的中文原因。
    """
    if not config.configured:
        return False, "密钥未配置，无法生成。"

    try:
        from openai import OpenAI
    except ImportError:
        return False, "缺少 openai 依赖。"

    try:
        client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=timeout)
        resp = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return True, (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        return False, _explain(exc, config.model)
