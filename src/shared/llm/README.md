# Lumidoc 共享 LLM 库

本库提供了Lumidoc项目中使用大语言模型的统一接口和工具。它作为共享基础设施提供给所有微服务。

## 设计原则

- **统一配置**：所有LLM相关配置从环境变量加载，确保一致性
- **多模型支持**：支持Ollama、OpenAI、Deepseek、vLLM等多种模型提供商
- **适配器模式**：使用适配器模式统一不同模型的接口
- **LangChain集成**：提供与LangChain框架的无缝集成
- **向后兼容**：保留原有的`LLMClient`以支持平滑迁移
- **高并发支持**：通过vLLM适配器支持高并发请求处理

## 主要组件

### 配置 

配置通过`src/shared/config`模块提供：

```python
from src.shared.config import llm_settings, MODEL_TYPE_OLLAMA

# 使用配置
print(f"当前模型类型: {llm_settings.model_type}")
print(f"当前模型名称: {llm_settings.model_name}")
```

### 适配器 (`adapters/`)

提供统一的LLM适配器接口：

```python
from src.shared.llm import create_llm_adapter

# 创建适配器
adapter = create_llm_adapter()

# 生成文本
text = await adapter.generate("你好，请介绍一下自己")
```

### vLLM适配器 (`vllm_adapter.py`)

提供高并发LLM请求支持：

```python
from src.shared.llm import create_llm_adapter, MODEL_TYPE_VLLM

# 创建vLLM适配器
adapter = create_llm_adapter(model_type=MODEL_TYPE_VLLM)

# 生成文本
text = await adapter.generate("你好，请介绍一下自己")
```

### LangChain集成 (`langchain.py`)

提供与LangChain框架的集成：

```python
from src.shared.llm import LumidocLangChainLLM
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

# 创建LLM
llm = LumidocLangChainLLM()

# 创建提示模板
prompt = PromptTemplate(
    input_variables=["query"],
    template="请回答以下问题：{query}"
)

# 创建链
chain = LLMChain(llm=llm, prompt=prompt)

# 运行链
result = await chain.arun(query="什么是微服务架构？")
```

### 客户端 (`client.py`)

提供向后兼容的客户端（不推荐使用）：

```python
from src.shared.llm import LLMClient

# 创建客户端
client = LLMClient()

# 生成文本
text = await client.generate("你好，请介绍一下自己")
```

## 配置参数

所有配置参数通过环境变量设置：

```
# LLM配置
LLM_MODEL_TYPE=ollama         # 模型类型：ollama/openai/deepseek/vllm
LLM_MODEL_NAME=llama3         # 模型名称
LLM_API_KEY=your-api-key      # API密钥（在线模型需要）
LLM_TEMPERATURE=0.7           # 温度参数
LLM_MAX_TOKENS=2000           # 最大生成token数
LLM_REQUEST_TIMEOUT=60.0      # 请求超时时间(秒)

# API端点
OLLAMA_API_URL=http://localhost:11434
OPENAI_API_URL=https://api.openai.com/v1
DEEPSEEK_API_URL=https://api.deepseek.com
VLLM_API_URL=http://localhost:8000

# vLLM特有配置
VLLM_TENSOR_PARALLEL_SIZE=1          # 张量并行大小
VLLM_MAX_CONCURRENT_REQUESTS=100      # 最大并发请求数
VLLM_GPU_MEMORY_UTILIZATION=0.9       # GPU内存利用率
```

## 使用示例

### 基本使用

```python
import asyncio
from src.shared.llm import create_llm_adapter

async def main():
    # 创建适配器
    adapter = create_llm_adapter()
    
    # 生成文本
    result = await adapter.generate(
        prompt="你好，请介绍一下自己",
        system_prompt="你是一个专业的助手",
        temperature=0.7,
        max_tokens=1000
    )
    
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

### 使用vLLM进行高并发处理

```python
import asyncio
from src.shared.llm import create_llm_adapter, MODEL_TYPE_VLLM

async def process_batch(prompts):
    # 创建vLLM适配器
    adapter = create_llm_adapter(model_type=MODEL_TYPE_VLLM)
    
    # 并发处理多个请求
    tasks = [adapter.generate(prompt) for prompt in prompts]
    results = await asyncio.gather(*tasks)
    
    return results

async def main():
    prompts = [
        "解释什么是微服务架构",
        "Python的异步编程有什么优势",
        "如何实现高并发系统",
        "分布式系统面临的主要挑战"
    ]
    
    results = await process_batch(prompts)
    for i, result in enumerate(results):
        print(f"问题 {i+1}: {prompts[i]}")
        print(f"回答: {result}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

### 在微服务中使用

```python
from src.shared.llm import LumidocLangChainLLM
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

class MyProcessor:
    def __init__(self):
        self.llm = LumidocLangChainLLM()
        self.prompt = PromptTemplate(
            input_variables=["query"],
            template="请回答以下问题：{query}"
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    async def process(self, query: str) -> str:
        return await self.chain.arun(query=query)
``` 