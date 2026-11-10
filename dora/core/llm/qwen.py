"""
Qwen (通义千问) LLM 客户端（OpenAI 兼容格式）
Qwen API 完全兼容 OpenAI 接口格式，直接继承 OpenAICompatibleLLM
"""

from core.llm.openai_compatible import OpenAICompatibleLLM


class QwenLLM(OpenAICompatibleLLM):
    """
    Qwen LLM 客户端

    Qwen（通义千问）API 兼容 OpenAI 格式，只需配置对应的 base_url 和 model_name。

    配置示例（settings.yaml）:
        llm:
          provider: qwen
          api_key: "your-qwen-api-key"
          base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
          model_name: "qwen-plus"
    """
    pass
