"""
DeepSeek LLM 客户端（OpenAI 兼容格式）
DeepSeek API 完全兼容 OpenAI 接口格式，直接继承 OpenAICompatibleLLM
"""

from core.llm.openai_compatible import OpenAICompatibleLLM


class DeepSeekLLM(OpenAICompatibleLLM):
    """
    DeepSeek LLM 客户端

    DeepSeek API 完全兼容 OpenAI 格式，只需配置对应的 base_url 和 model_name。

    配置示例（settings.yaml）:
        llm:
          provider: deepseek
          api_key: "your-deepseek-api-key"
          base_url: "https://api.deepseek.com/v1"
          model_name: "deepseek-chat"
    """
    pass
