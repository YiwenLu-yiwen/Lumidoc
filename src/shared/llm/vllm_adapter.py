#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
vLLM适配器
提供与vLLM服务交互的接口，支持高并发请求
"""

import json
import aiohttp
from typing import Dict, List, Any, Optional, Union, AsyncIterator

from src.shared.config import llm_settings
from .base_adapter import BaseLLMAdapter, Message, CompletionOptions

class VLLMAdapter(BaseLLMAdapter):
    """vLLM适配器，支持高并发请求处理"""

    def __init__(self,
                 api_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 model_name: Optional[str] = None,
                 **kwargs):
        """
        初始化vLLM适配器

        Args:
            api_url: vLLM API地址
            api_key: API密钥（如果需要）
            model_name: 模型名称
            **kwargs: 其他参数
        """
        self.api_url = api_url or llm_settings.vllm_api_url
        self.api_key = api_key or llm_settings.api_key
        self.model_name = model_name or llm_settings.model_name
        self.session = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """确保aiohttp会话已创建"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def _prepare_headers(self) -> Dict[str, str]:
        """准备请求头"""
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _convert_messages_to_prompt(self, messages: List[Message]) -> str:
        """将消息列表转换为提示文本"""
        prompt = ""
        for message in messages:
            if message["role"] == "system":
                prompt += f"<|system|>\n{message['content']}\n"
            elif message["role"] == "user":
                prompt += f"<|user|>\n{message['content']}\n"
            elif message["role"] == "assistant":
                prompt += f"<|assistant|>\n{message['content']}\n"
        prompt += "<|assistant|>\n"
        return prompt

    async def generate(self,
                       prompt: str,
                       system_prompt: Optional[str] = None,
                       **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 提示文本
            system_prompt: 系统提示文本
            **kwargs: 其他参数

        Returns:
            生成的文本
        """
        options = CompletionOptions(
            temperature=kwargs.get("temperature", llm_settings.temperature),
            max_tokens=kwargs.get("max_tokens", llm_settings.max_tokens),
            timeout=kwargs.get("timeout", llm_settings.request_timeout),
            stop_sequences=kwargs.get("stop", [])
        )

        # 如果有系统提示，构建消息列表
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            return await self.chat(messages, **kwargs)

        session = await self._ensure_session()

        payload = {
            "prompt": prompt,
            "max_tokens": options.max_tokens,
            "temperature": options.temperature,
            "stop": options.stop_sequences or [],
        }

        try:
            async with session.post(
                f"{self.api_url}/v1/completions",
                headers=self._prepare_headers(),
                json=payload,
                timeout=options.timeout
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"vLLM API错误: {response.status} - {error_text}")

                result = await response.json()
                return result["choices"][0]["text"]
        except Exception as e:
            raise RuntimeError(f"vLLM生成失败: {str(e)}")

    async def generate_stream(self,
                             prompt: str,
                             system_prompt: Optional[str] = None,
                             **kwargs) -> AsyncIterator[str]:
        """
        流式生成文本

        Args:
            prompt: 提示文本
            system_prompt: 系统提示文本
            **kwargs: 其他参数

        Yields:
            生成的文本片段
        """
        options = CompletionOptions(
            temperature=kwargs.get("temperature", llm_settings.temperature),
            max_tokens=kwargs.get("max_tokens", llm_settings.max_tokens),
            timeout=kwargs.get("timeout", llm_settings.request_timeout),
            stop_sequences=kwargs.get("stop", [])
        )

        # 如果有系统提示，构建消息列表
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            async for chunk in self.chat_stream(messages, **kwargs):
                yield chunk
            return

        session = await self._ensure_session()

        payload = {
            "prompt": prompt,
            "max_tokens": options.max_tokens,
            "temperature": options.temperature,
            "stop": options.stop_sequences or [],
            "stream": True
        }

        try:
            async with session.post(
                f"{self.api_url}/v1/completions",
                headers=self._prepare_headers(),
                json=payload,
                timeout=options.timeout
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"vLLM API错误: {response.status} - {error_text}")

                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        data = json.loads(line[6:])
                        if "choices" in data and len(data["choices"]) > 0:
                            yield data["choices"][0]["text"]
        except Exception as e:
            raise RuntimeError(f"vLLM流式生成失败: {str(e)}")

    async def chat(self,
                  messages: List[Dict[str, str]],
                  **kwargs) -> str:
        """
        聊天完成

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Returns:
            生成的回复
        """
        options = CompletionOptions(
            temperature=kwargs.get("temperature", llm_settings.temperature),
            max_tokens=kwargs.get("max_tokens", llm_settings.max_tokens),
            timeout=kwargs.get("timeout", llm_settings.request_timeout),
            stop_sequences=kwargs.get("stop", [])
        )

        session = await self._ensure_session()

        # vLLM可能不直接支持聊天格式，转换为提示文本
        if self._supports_chat_api():
            # 如果支持聊天API
            payload = {
                "model": self.model_name,
                "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                "max_tokens": options.max_tokens,
                "temperature": options.temperature,
                "stop": options.stop_sequences or [],
            }

            try:
                async with session.post(
                    f"{self.api_url}/v1/chat/completions",
                    headers=self._prepare_headers(),
                    json=payload,
                    timeout=options.timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"vLLM API错误: {response.status} - {error_text}")

                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
            except Exception as e:
                raise RuntimeError(f"vLLM聊天失败: {str(e)}")
        else:
            # 如果不支持聊天API，转换为提示文本
            prompt = self._convert_messages_to_prompt(messages)
            return await self.generate(prompt, options=options)

    async def chat_stream(self,
                         messages: List[Dict[str, str]],
                         **kwargs) -> AsyncIterator[str]:
        """
        流式聊天完成

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Yields:
            生成的回复片段
        """
        options = CompletionOptions(
            temperature=kwargs.get("temperature", llm_settings.temperature),
            max_tokens=kwargs.get("max_tokens", llm_settings.max_tokens),
            timeout=kwargs.get("timeout", llm_settings.request_timeout),
            stop_sequences=kwargs.get("stop", [])
        )

        session = await self._ensure_session()

        # vLLM可能不直接支持聊天格式，转换为提示文本
        if self._supports_chat_api():
            # 如果支持聊天API
            payload = {
                "model": self.model_name,
                "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
                "max_tokens": options.max_tokens,
                "temperature": options.temperature,
                "stop": options.stop_sequences or [],
                "stream": True
            }

            try:
                async with session.post(
                    f"{self.api_url}/v1/chat/completions",
                    headers=self._prepare_headers(),
                    json=payload,
                    timeout=options.timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"vLLM API错误: {response.status} - {error_text}")

                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith("data: ") and line != "data: [DONE]":
                            data = json.loads(line[6:])
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    yield delta["content"]
            except Exception as e:
                raise RuntimeError(f"vLLM流式聊天失败: {str(e)}")
        else:
            # 如果不支持聊天API，转换为提示文本
            prompt = self._convert_messages_to_prompt(messages)
            async for chunk in self.generate_stream(prompt, options=options):
                yield chunk

    async def create_embedding(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        创建文本嵌入

        Args:
            texts: 文本或文本列表

        Returns:
            List[List[float]]: 嵌入向量列表
        """
        session = await self._ensure_session()

        # 确保texts是列表
        if isinstance(texts, str):
            texts = [texts]

        try:
            async with session.post(
                f"{self.api_url}/v1/embeddings",
                headers=self._prepare_headers(),
                json={
                    "input": texts,
                    "model": f"{self.model_name}-embedding" if "-embedding" not in self.model_name else self.model_name
                },
                timeout=llm_settings.request_timeout
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"vLLM嵌入API错误: {response.status} - {error_text}")

                result = await response.json()

                # 处理OpenAI格式响应
                if "data" in result:
                    embeddings = []
                    for item in result["data"]:
                        if "embedding" in item:
                            embeddings.append(item["embedding"])
                    return embeddings

                return []
        except Exception:
            # 如果vLLM不支持嵌入，返回空列表
            return [[] for _ in texts]

    @property
    def model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            Dict[str, Any]: 模型信息
        """
        return {
            "name": self.model_name,
            "type": "vllm",
            "api_url": self.api_url,
            "supports_chat": self._supports_chat_api(),
            "supports_streaming": True,
            "supports_embeddings": False,  # vLLM通常不直接支持嵌入
            "max_tokens": llm_settings.max_tokens,
            "temperature": llm_settings.temperature
        }

    def _supports_chat_api(self) -> bool:
        """检查是否支持聊天API"""
        # 根据模型名称或其他条件判断是否支持聊天API
        # 这里简单地假设所有模型都支持
        return True
