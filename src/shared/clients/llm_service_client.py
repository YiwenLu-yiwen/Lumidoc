"""
统一的LLM服务客户端
严格遵循微服务架构原则，只通过Gateway调用LLM服务
"""

import os
import logging
import asyncio
import json
from typing import Dict, Any, Optional, List, AsyncGenerator
import httpx

# 配置日志
logger = logging.getLogger(__name__)

# 默认超时设置
DEFAULT_TIMEOUT = float(os.getenv('LLM_REQUEST_TIMEOUT', '7200.0'))  # 默认2小时，适配本地模型

# 定义重试参数
MAX_RETRIES = 1  # 本地模型稳定，减少重试次数
RETRY_DELAY = 1  # 秒

class LLMServiceClient:
    """
    统一的LLM服务客户端
    严格遵循微服务架构原则，只通过Gateway调用LLM服务
    """

    _instance = None

    @classmethod
    async def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """初始化LLM服务客户端"""
        self.timeout = DEFAULT_TIMEOUT
        self.gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8888")
        self.service_token = os.environ.get("SERVICE_AUTH_TOKEN")
        if not self.service_token:
            raise RuntimeError("SERVICE_AUTH_TOKEN is required")

        logger.info(f"初始化LLM服务客户端，Gateway: {self.gateway_url}")

    async def chat_generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        生成聊天回复

        Args:
            messages: 消息列表，格式为[{"role": "user", "content": "..."}]
            **kwargs: 其他参数

        Returns:
            str: 生成的回复
        """
        try:
            # 输入验证
            if not messages or not isinstance(messages, list):
                raise ValueError("messages必须是非空列表")

            # 验证消息格式
            for msg in messages:
                if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                    raise ValueError("每条消息必须包含role和content字段")

            # 调用LLM服务
            response = await self._call_service("chat", {
                "messages": messages,
                **kwargs
            })

            # 响应处理
            if isinstance(response, dict):
                if "message" in response and isinstance(response["message"], dict) and "content" in response["message"]:
                    return response["message"]["content"]
                elif "content" in response:
                    return response["content"]
                elif "data" in response:
                    if isinstance(response["data"], dict) and "content" in response["data"]:
                        return response["data"]["content"]
                    elif isinstance(response["data"], str):
                        return response["data"]
                elif "text" in response:
                    return response["text"]
                else:
                    logger.warning(f"LLM服务响应格式异常: {response}")
                    raise Exception(f"LLM服务响应格式异常: {response}")
            elif isinstance(response, str):
                return response
            else:
                raise Exception(f"LLM服务返回未知格式: {type(response)}")

        except Exception as e:
            logger.error(f"聊天生成失败: {str(e)}")
            # 区分不同类型的错误并重新抛出
            if "连接" in str(e) or "timeout" in str(e).lower():
                raise Exception(f"LLM服务连接失败: {str(e)}")
            elif "服务发现" in str(e):
                raise Exception(f"LLM服务发现失败: {str(e)}")
            else:
                raise Exception(f"LLM服务调用错误: {str(e)}")

    async def generate_text(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 提示词
            **kwargs: 其他参数

        Returns:
            str: 生成的文本
        """
        try:
            # 构建请求数据
            data = {
                "prompt": prompt,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 1024),
                "stream": kwargs.get("stream", False)
            }

            # 调用服务
            result = await self._call_service("generate", data)

            if isinstance(result, dict) and "text" in result:
                return result["text"]
            elif isinstance(result, str):
                return result
            else:
                logger.warning(f"生成文本返回格式异常: {result}")
                return ""
        except Exception as e:
            logger.error(f"生成文本失败: {str(e)}")
            raise

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        获取文本嵌入向量

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 嵌入向量列表
        """
        try:
            # 构建请求数据
            data = {
                "texts": texts,
                "model": os.getenv(
                    "DEFAULT_EMBEDDING_MODEL",
                    os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
                ),
            }

            # 调用服务
            result = await self._call_service("embeddings", data)

            if isinstance(result, dict) and "embeddings" in result:
                return result["embeddings"]
            else:
                logger.warning(f"获取嵌入向量返回格式异常: {result}")
                return []
        except Exception as e:
            logger.error(f"获取嵌入向量失败: {str(e)}")
            raise

    async def extract_triples(self, content: str) -> List[Dict[str, str]]:
        """
        提取三元组

        Args:
            content: 文本内容

        Returns:
            List[Dict[str, str]]: 三元组列表
        """
        try:
            # 构建请求数据
            data = {"content": content}

            # 调用服务
            result = await self._call_service("triples", data)

            if isinstance(result, dict) and "triples" in result:
                return result["triples"]
            else:
                logger.warning(f"提取三元组返回格式异常: {result}")
                return []
        except Exception as e:
            logger.error(f"提取三元组失败: {str(e)}")
            raise

    async def stream_generate(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        流式生成回复

        Args:
            prompt: 输入提示
            **kwargs: 其他参数

        Yields:
            str: 生成的文本片段
        """
        try:
            # 构建请求数据，使用prompt字段而不是messages
            data = {
                "prompt": prompt,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 1024),
                "stream": True
            }

            # 使用聊天接口保留消息结构及用户选择的模型。
            messages = kwargs.get("messages")
            if messages is not None:
                data.pop("prompt")
                data["messages"] = messages
            if kwargs.get("model"):
                data["model"] = kwargs["model"]

            # 设置请求头，包含服务间认证
            headers = {"Content-Type": "application/json"}
            headers["Authorization"] = f"Service {self.service_token}"

            # 配置详细的超时设置，避免ReadTimeout错误
            timeout_config = httpx.Timeout(
                connect=30.0,    # 连接超时30秒
                read=300.0,      # 读取超时5分钟，适应LLM响应时间
                write=60.0,      # 写入超时1分钟
                pool=30.0        # 连接池超时30秒
            )
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                endpoint = "chat" if messages is not None else "generate"
                api_url = f"{self.gateway_url}/api/v1/llm/{endpoint}"

                async with client.stream(
                    "POST",
                    api_url,
                    json=data,
                    headers=headers
                ) as response:
                    if response.status_code == 200:
                        logger.debug("开始处理流式响应")
                        async for line in response.aiter_lines():
                            # SSE 注释心跳不是模型正文。
                            if line.startswith(":"):
                                continue
                            if line.strip():
                                try:
                                    # 处理SSE格式
                                    if line.startswith("data: "):
                                        line = line[6:]  # 移除"data: "前缀

                                    if line.strip() == "[DONE]":
                                        break

                                    # 解析JSON数据
                                    chunk_data = json.loads(line)

                                    # 提取内容
                                    if isinstance(chunk_data, dict):
                                        if "content" in chunk_data:
                                            yield chunk_data["content"]
                                        elif "text" in chunk_data:
                                            yield chunk_data["text"]
                                        elif "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                            delta = chunk_data["choices"][0].get("delta", {})
                                            if "content" in delta:
                                                yield delta["content"]
                                    else:
                                        yield str(chunk_data)

                                except json.JSONDecodeError:
                                    # 如果不是JSON格式，直接输出
                                    if line.strip():
                                        yield line.strip()
                                except Exception as e:
                                    logger.error(f"处理流式响应块失败: {str(e)}")
                                    continue
                    else:
                        error_text = await response.aread()
                        logger.error(f"流式请求失败 - 状态: {response.status_code}, 响应: {error_text}")
                        yield f"流式请求失败: {response.status_code} - {error_text.decode()}"

        except Exception as e:
            logger.error(f"流式生成失败: {str(e)}")
            yield f"流式生成失败: {str(e)}"

    async def _call_service(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用服务，严格遵循项目原则：统一通过Gateway进行服务调用

        Args:
            endpoint: 端点名称
            data: 请求数据

        Returns:
            Dict[str, Any]: 服务响应
        """
        try:
            logger.debug(f"通过Gateway调用LLM服务: {endpoint}")

            # 设置请求头，包含服务间认证
            headers = {"Content-Type": "application/json"}
            headers["Authorization"] = f"Service {self.service_token}"

            # 配置详细的超时设置，避免ReadTimeout错误
            timeout_config = httpx.Timeout(
                connect=30.0,    # 连接超时30秒
                read=300.0,      # 读取超时5分钟，适应LLM响应时间
                write=60.0,      # 写入超时1分钟
                pool=30.0        # 连接池超时30秒
            )
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                api_url = f"{self.gateway_url}/api/v1/llm/{endpoint}"

                response = await client.post(
                    api_url,
                    json=data,
                    headers=headers
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.debug(f"Gateway调用LLM服务成功: {endpoint}")
                    return result
                else:
                    error_text = response.text
                    logger.error(f"Gateway调用失败 - 状态: {response.status_code}, 响应: {error_text}")
                    raise Exception(f"Gateway调用失败: {response.status_code} - {error_text}")

        except Exception as e:
            logger.error(f"通过Gateway调用LLM服务失败: {str(e)}")
            raise Exception(f"LLM服务调用失败: {str(e)}")

# 移除默认客户端实例，统一使用单例模式
# default_client = LLMServiceClient()

async def generate_chat_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    history_messages: List[Dict[str, str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024
) -> str:
    """
    直接调用LLM服务生成回答

    Args:
        prompt: 用户提示词
        system_prompt: 系统提示词
        history_messages: 历史消息
        temperature: 温度参数
        max_tokens: 最大生成token数量

    Returns:
        str: 生成的回答
    """
    if history_messages is None:
        history_messages = []

    try:
        # 获取LLM服务客户端
        client = await LLMServiceClient.get_instance()

        # 构建消息
        messages = []

        # 添加系统消息
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加历史消息
        if history_messages:
            for msg in history_messages:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    messages.append(msg)
                elif isinstance(msg, str):
                    # 如果是字符串，假设是用户消息
                    messages.append({"role": "user", "content": msg})

        # 添加用户提示词
        messages.append({"role": "user", "content": prompt})

        # 调用LLM生成回答
        for retry in range(MAX_RETRIES):
            try:
                result = await client.chat_generate(messages, temperature=temperature, max_tokens=max_tokens)

                # 检查结果有效性
                if isinstance(result, str) and result.strip():
                    return result
                else:
                    logger.warning(f"LLM服务返回空结果: {result}")
                    if retry < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    else:
                        raise Exception("LLM服务返回空结果")

            except Exception as e:
                logger.warning(f"LLM服务调用失败 (尝试 {retry+1}/{MAX_RETRIES}): {str(e)}")
                if retry < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    # 提供更好的错误信息
                    raise Exception(f"LLM服务调用失败 (重试{MAX_RETRIES}次): {str(e)}")

        # 这行不会执行到，但为了满足返回类型检查
        raise Exception("未知错误")

    except Exception as e:
        logger.error(f"生成聊天回答失败: {str(e)}")
        # 抛出更详细的错误信息
        raise Exception(f"LLM服务不可用: {str(e)}")

async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    直接调用LLM服务获取文本嵌入向量

    Args:
        texts: 文本列表

    Returns:
        List[List[float]]: 嵌入向量列表
    """
    try:
        # 获取LLM服务客户端
        client = await LLMServiceClient.get_instance()

        # 调用嵌入接口
        for retry in range(MAX_RETRIES):
            try:
                return await client.get_embeddings(texts)
            except Exception as e:
                logger.warning(f"嵌入服务调用失败 (尝试 {retry+1}/{MAX_RETRIES}): {str(e)}")
                if retry < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    raise

        # 这行不会执行到，但为了满足返回类型检查
        raise Exception("未知错误")

    except Exception as e:
        logger.error(f"获取嵌入向量失败: {str(e)}")
        raise

async def extract_triples(text: str, temperature: float = 0.2) -> str:
    """
    从文本中提取三元组

    Args:
        text: 输入文本
        temperature: 温度参数

    Returns:
        str: 提取的三元组JSON字符串
    """
    system_prompt = "你是一个专业的知识图谱构建专家，擅长从文本中提取实体和关系。"
    user_prompt = f"""请从以下文本中提取实体和关系，并按以下JSON格式返回:
    {{
        "entities": [
            {{"entity": "实体名称", "type": "实体类型", "description": "实体描述"}}
        ],
        "relationships": [
            {{"source": "源实体", "target": "目标实体", "description": "关系描述", "keywords": "关键词,用逗号分隔"}}
        ]
    }}

    文本内容: {text}
    """

    return await generate_chat_response(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature
    )
