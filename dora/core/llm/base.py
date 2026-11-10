"""
基础 LLM 抽象类
定义所有 LLM 客户端必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional


class BaseLLM(ABC):
    """LLM 客户端抽象基类"""

    def __init__(self, llm_cfg: Dict[str, Any]) -> None:
        """
        初始化 LLM 客户端

        Args:
            llm_cfg: LLM 配置字典
        """
        self.api_key = llm_cfg.get("api_key", "")
        self.base_url = llm_cfg.get("base_url", "")
        self.model_name = llm_cfg.get("model_name", "")
        self.temperature = llm_cfg.get("temperature", 0.1)
        self.max_tokens = llm_cfg.get("max_tokens", 2048)
        self.timeout = llm_cfg.get("timeout", 60)
        self.max_retries = llm_cfg.get("max_retries", 3)

    @abstractmethod
    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        非流式对话，一次性返回完整结果

        Args:
            prompt: 用户输入提示
            system_prompt: 系统提示（可选）
            **kwargs: 额外参数

        Returns:
            模型生成的完整回复文本
        """
        pass

    @abstractmethod
    def stream_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        流式对话，逐块返回生成结果

        Args:
            prompt: 用户输入提示
            system_prompt: 系统提示（可选）
            **kwargs: 额外参数

        Yields:
            逐块生成的文本片段
        """
        pass

    @abstractmethod
    def chat_with_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any
    ) -> str:
        """
        使用消息列表进行对话（支持多轮对话历史）

        Args:
            messages: 消息列表，格式为 [{"role": "user"/"assistant"/"system", "content": "..."}]
            **kwargs: 额外参数

        Returns:
            模型生成的完整回复文本
        """
        pass
