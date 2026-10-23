"""环境自检 —— 一张页面回答"密钥到底通没通"。

放在 pages/ 下是为了让作者随时能自查，评委也能看到工程规范。
它不参与业务流程，只读配置、发一次最小请求。
"""
import streamlit as st

from core.ai_client import load_config, ping

st.title("环境自检")
st.caption("检查模型密钥配置与实际连通性。本页不发业务请求，只做一次 8 token 的探测。")

config = load_config()

left, right = st.columns([1.15, 1])

with left:
    st.subheader("配置读取结果")

    if config.state == "ok":
        st.success(f"已读到密钥，来源：{config.source}")
    elif config.state == "placeholder":
        st.warning(f"文件找到了（{config.source}），但里面还是模板原文，密钥没填进去。")
    elif config.state == "invalid":
        st.warning(
            f"密钥只有 {len(config.api_key.strip())} 位，疑似复制不全。"
            "正常的 DeepSeek 密钥是 sk- 开头的一长串。"
        )
    else:
        st.error("没有读到密钥（查找位置：Streamlit Secrets、.env、环境变量）")

    st.dataframe(
        [
            {"配置项": "API Key", "当前值": config.masked_key, "说明": "程序进门的凭证"},
            {"配置项": "BASE_URL", "当前值": config.base_url, "说明": "请求发往哪个服务"},
            {"配置项": "MODEL", "当前值": config.model, "说明": "用哪个模型"},
        ],
        hide_index=True,
        width="stretch",
    )

with right:
    st.subheader("连通性测试")
    st.write("点一下按钮，让模型回一句话。**能回话才算真的开通。**")

    if st.button("测试连接", type="primary", disabled=not config.configured):
        with st.spinner("正在请求…"):
            ok, message = ping(config)
        if ok:
            st.success(message)
            st.balloons()
        else:
            st.error(message)
    elif not config.configured:
        st.info("先配置密钥，按钮才会亮。")

st.divider()

with st.expander("怎么配置（本地 / 云端两种情况）", expanded=not config.configured):
    st.markdown(
        """
**本地开发** —— 在项目根目录建 `.env`：

```ini
OPENAI_API_KEY=sk-你的密钥
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

**Streamlit Cloud** —— 应用页面右下角 `⋮` → Settings → Secrets，粘贴：

```toml
OPENAI_API_KEY = "sk-你的密钥"
OPENAI_BASE_URL = "https://api.deepseek.com/v1"
OPENAI_MODEL = "deepseek-chat"
```

保存后应用自动重启。注意云端读不到本地的 `.env`，因为它在 `.gitignore` 里。
"""
    )

with st.expander("常见报错对照"):
    st.dataframe(
        [
            {"提示": "401 / invalid_api_key", "原因": "密钥错了或已吊销", "处理": "回控制台重新生成"},
            {"提示": "402 / Insufficient Balance", "原因": "余额不足", "处理": "充值，DeepSeek 最低 10 元"},
            {"提示": "404 / model_not_found", "原因": "模型名拼错", "处理": "DeepSeek 用 deepseek-chat"},
            {"提示": "超时", "原因": "网络或 BASE_URL 错误", "处理": "检查地址末尾是否 /v1"},
        ],
        hide_index=True,
        width="stretch",
    )

st.caption(
    "说明：本页只验证「配置是否生效」，不验证模型判断质量。"
    "后者要靠固定的测试样本对比，是另一件事。"
)
