"""热门 AI 服务商预设：选中服务商后只需填 API Key。

所有预设都是 OpenAI 兼容接口。模型名可能随服务商更新，
如果「测试连接」提示模型不存在，可在「高级设置」里换成最新模型名。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    base_url: str
    vision_model: str
    text_model: str
    hint: str = ""
    key_placeholder: str = "粘贴你的 API Key"


PROVIDERS: list[Provider] = [
    Provider(
        "deepseek",
        "DeepSeek（深度求索）",
        "https://api.deepseek.com",
        "deepseek-flash",
        "deepseek-flash",
        "官方 API 已原生支持图片输入，国内直连、价格便宜；在 platform.deepseek.com 创建 API Key。",
    ),
    Provider(
        "dashscope",
        "通义千问（阿里云百炼）",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-vl-max",
        "qwen-plus",
        "在阿里云百炼控制台创建 API Key，新用户一般有免费额度，国内速度稳定。",
    ),
    Provider(
        "zhipu",
        "智谱 GLM",
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-4.5v",
        "glm-4.5-flash",
        "在 open.bigmodel.cn 创建 API Key；glm-4.5-flash 文本模型目前免费。",
    ),
    Provider(
        "siliconflow",
        "硅基流动 SiliconFlow",
        "https://api.siliconflow.cn/v1",
        "Qwen/Qwen2.5-VL-32B-Instruct",
        "Qwen/Qwen2.5-7B-Instruct",
        "在 siliconflow.cn 创建 API Key，注册通常送额度，国内可选模型多、便宜。",
    ),
    Provider(
        "moonshot",
        "Kimi（月之暗面）",
        "https://api.moonshot.cn/v1",
        "moonshot-v1-8k-vision-preview",
        "moonshot-v1-8k",
        "在 platform.moonshot.cn 创建 API Key。",
    ),
    Provider(
        "ark",
        "火山方舟（豆包）",
        "https://ark.cn-beijing.volces.com/api/v3",
        "doubao-1.5-vision-pro-32k",
        "doubao-1.5-pro-32k",
        "在火山方舟控制台创建 API Key；如果用接入点，把模型名换成 ep- 开头的接入点 ID。",
    ),
    Provider(
        "hunyuan",
        "腾讯混元",
        "https://api.hunyuan.cloud.tencent.com/v1",
        "hunyuan-vision",
        "hunyuan-turbo",
        "在腾讯云混元控制台创建 API Key。",
    ),
    Provider(
        "qianfan",
        "百度千帆（文心）",
        "https://qianfan.baidubce.com/v2",
        "ernie-4.5-turbo-vl",
        "ernie-4.5-turbo-128k",
        "在百度智能云千帆控制台创建 API Key。",
    ),
    Provider(
        "openai",
        "OpenAI（ChatGPT）",
        "https://api.openai.com/v1",
        "gpt-4o-mini",
        "gpt-4o-mini",
        "在 platform.openai.com 创建 API Key；gpt-4o-mini 便宜够用，国内访问可能需要代理。",
    ),
    Provider(
        "ollama",
        "本地 Ollama（离线免费）",
        "http://localhost:11434/v1",
        "qwen2.5vl:7b",
        "qwen2.5:7b",
        "需要先安装 Ollama 并下载对应模型；数据完全不出本机，但比较吃显卡。API Key 随便填即可。",
        key_placeholder="随便填，例如 ollama",
    ),
]

CUSTOM = Provider(
    "custom",
    "自定义（手动填写接口）",
    "",
    "",
    "",
    "填写任何 OpenAI 兼容接口的地址（以 /v1 结尾）和模型名。",
)


def all_providers() -> list[Provider]:
    return [*PROVIDERS, CUSTOM]


def provider_by_key(key: str) -> Provider | None:
    for provider in all_providers():
        if provider.key == key:
            return provider
    return None


def match_provider(base_url: str) -> Provider | None:
    """根据接口地址反推服务商。"""
    normalized = (base_url or "").strip().rstrip("/").lower()
    if not normalized:
        return None
    for provider in PROVIDERS:
        if provider.base_url.strip().rstrip("/").lower() == normalized:
            return provider
    return None
