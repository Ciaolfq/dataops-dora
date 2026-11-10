"""
AIHubMix Claude LLM 客户端（OpenAI 兼容格式）
AIHubMix 提供 Claude 模型的 OpenAI 兼容接口
"""

from core.llm.openai_compatible import OpenAICompatibleLLM


class AIHubMixClaudeLLM(OpenAICompatibleLLM):
    """
    AIHubMix Claude LLM 客户端

    AIHubMix 通过 OpenAI 兼容格式提供 Claude 模型访问。

    配置示例（settings.yaml）:
        llm:
          provider: aihubmix_claude
          api_key: "your-aihubmix-api-key"
          base_url: "https://aihubmix.com/v1"
          model_name: "claude-sonnet-4-6"
    """
    pass
