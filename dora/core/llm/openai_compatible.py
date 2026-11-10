"""
OpenAI 兼容格式的 LLM 客户端
支持所有兼容 OpenAI API 格式的大模型服务（DeepSeek、Qwen、GPT、AIHubMix 等）
支持流式和非流式调用，带自动重试机制
"""

import json
import time
from typing import Any, Dict, Iterator, List, Optional

import requests

from core.llm.base import BaseLLM
from utils.logger import logger


class OpenAICompatibleLLM(BaseLLM):
    """
    OpenAI 兼容格式 LLM 客户端

    支持的特性：
    - 流式 / 非流式调用
    - 多轮对话消息格式
    - 自动重试（指数退避）
    - 错误处理与日志记录
    """

    def __init__(self, llm_cfg: Dict[str, Any]) -> None:
        super().__init__(llm_cfg)
        self._validate_config()

    def _validate_config(self) -> None:
        """验证必要的配置项"""
        if not self.api_key or self.api_key == "your-api-key-here":
            logger.warning(
                "LLM api_key 未配置或使用占位符。"
                "请设置环境变量 DEEPSEEK_API_KEY 或在 settings.yaml 中配置。"
            )
        if not self.base_url:
            raise ValueError("LLM base_url 必须配置")
        if not self.model_name:
            raise ValueError("LLM model_name 必须配置")

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        构建请求 payload

        Args:
            messages: 消息列表
            stream: 是否流式
            **kwargs: 额外参数，会覆盖默认配置

        Returns:
            请求 payload 字典
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": stream,
        }

        # 移除 None 值
        return {k: v for k, v in payload.items() if v is not None}

    def _request_with_retry(
        self,
        payload: Dict[str, Any],
        stream: bool = False
    ) -> requests.Response:
        """
        带重试机制的 HTTP 请求

        Args:
            payload: 请求 payload
            stream: 是否流式

        Returns:
            requests Response 对象

        Raises:
            requests.RequestException: 所有重试失败后抛出
        """
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    url,
                    headers=self._build_headers(),
                    json=payload,
                    stream=stream,
                    timeout=self.timeout,
                )

                if resp.status_code == 200:
                    return resp

                logger.warning(
                    f"LLM 请求失败 (第 {attempt + 1}/{self.max_retries} 次), "
                    f"状态码: {resp.status_code}, 响应: {resp.text[:200]}"
                )

                if resp.status_code in (401, 403, 404):
                    raise requests.HTTPError(
                        f"LLM 请求失败: {resp.status_code} - {resp.text[:500]}"
                    )

            except requests.RequestException as e:
                last_exception = e
                logger.warning(
                    f"LLM 请求异常 (第 {attempt + 1}/{self.max_retries} 次): {str(e)}"
                )

            # 指数退避
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                time.sleep(wait_time)

        raise last_exception or requests.RequestException("LLM 请求失败，已耗尽重试次数")

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        非流式对话

        Args:
            prompt: 用户输入提示
            system_prompt: 系统提示（可选）
            **kwargs: 额外参数

        Returns:
            模型生成的完整回复文本
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.chat_with_messages(messages, **kwargs)

    def chat_with_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any
    ) -> str:
        """
        使用消息列表进行非流式对话

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            模型生成的完整回复文本
        """
        payload = self._build_payload(messages, stream=False, **kwargs)

        logger.debug(
            f"LLM 非流式请求 | model={self.model_name} | "
            f"messages_count={len(messages)}"
        )

        try:
            resp = self._request_with_retry(payload, stream=False)
            resp_json = resp.json()
            content = resp_json["choices"][0]["message"]["content"].strip()
            logger.debug(f"LLM 响应成功，内容长度: {len(content)}")
            return content
        except Exception as e:
            logger.error(f"LLM 非流式调用失败: {str(e)}")
            raise

    def stream_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        流式对话

        Args:
            prompt: 用户输入提示
            system_prompt: 系统提示（可选）
            **kwargs: 额外参数

        Yields:
            逐块生成的文本片段
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = self._build_payload(messages, stream=True, **kwargs)
        url = f"{self.base_url.rstrip('/')}/chat/completions"

        logger.debug(
            f"LLM 流式请求 | model={self.model_name} | "
            f"messages_count={len(messages)}"
        )

        try:
            resp = requests.post(
                url,
                headers=self._build_headers(),
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
            resp.raise_for_status()

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue

                # SSE 格式: "data: {...}"
                if line.startswith("data: "):
                    data_str = line[6:]  # 去掉 "data: " 前缀

                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

        except requests.RequestException as e:
            logger.error(f"LLM 流式调用失败: {str(e)}")
            raise
