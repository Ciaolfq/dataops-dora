"""
LLM 工厂类
根据配置动态创建对应的 LLM 客户端实例
"""

from typing import Any, Dict

from core.llm.base import BaseLLM
from utils.logger import logger


# 注册的 LLM 提供方
_LLM_REGISTRY: Dict[str, type] = {}


def register_llm(provider_name: str, llm_class: type) -> None:
    """
    注册一个 LLM 提供方

    Args:
        provider_name: 提供方名称（对应 settings.yaml 中的 provider 配置）
        llm_class: LLM 类（必须继承 BaseLLM）
    """
    _LLM_REGISTRY[provider_name.lower()] = llm_class


def create_llm(llm_cfg: Dict[str, Any]) -> BaseLLM:
    """
    根据配置创建 LLM 客户端实例

    Args:
        llm_cfg: LLM 配置字典，必须包含 provider 字段

    Returns:
        LLM 客户端实例

    Raises:
        ValueError: 未知的 provider 名称
    """
    provider = llm_cfg.get("provider", "openai_compatible").lower()

    if provider not in _LLM_REGISTRY:
        # 如果未注册，默认使用 OpenAI 兼容格式（大多数服务都兼容）
        logger.warning(
            f"未找到 LLM 提供方 '{provider}'，默认使用 OpenAI 兼容格式。"
            f"已注册的提供方: {list(_LLM_REGISTRY.keys())}"
        )
        from core.llm.openai_compatible import OpenAICompatibleLLM
        return OpenAICompatibleLLM(llm_cfg)

    llm_class = _LLM_REGISTRY[provider]
    logger.info(f"创建 LLM 客户端: provider={provider}, model={llm_cfg.get('model_name', 'unknown')}")
    return llm_class(llm_cfg)


# 注册内置提供方
def _register_builtin_llms() -> None:
    """注册所有内置 LLM 提供方"""
    from core.llm.openai_compatible import OpenAICompatibleLLM
    from core.llm.deepseek import DeepSeekLLM
    from core.llm.qwen import QwenLLM
    from core.llm.aihubmix_claude import AIHubMixClaudeLLM

    register_llm("openai_compatible", OpenAICompatibleLLM)
    register_llm("openai", OpenAICompatibleLLM)
    register_llm("deepseek", DeepSeekLLM)
    register_llm("qwen", QwenLLM)
    register_llm("aihubmix_claude", AIHubMixClaudeLLM)
    register_llm("claude", AIHubMixClaudeLLM)


# 初始化注册
_register_builtin_llms()
