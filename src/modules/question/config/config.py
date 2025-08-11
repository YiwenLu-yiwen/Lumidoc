"""
问答服务配置
使用统一配置系统
"""

import os
from pathlib import Path
from typing import Dict, Any
from src.shared.config import QuestionServiceSettings, get_env

# 创建全局设置实例
settings_base = QuestionServiceSettings()

class ExtendedQuestionSettings:
    """问答服务扩展配置，保持向后兼容性"""
    
    # 存储模式配置
    storage_mode: str = settings_base.storage_mode

    # LLM 配置
    llm_api_url: str = get_env("LLM_API_URL", "http://localhost:8000")
    llm_model_name: str = get_env("LLM_MODEL_NAME", "gpt-3.5-turbo")
    llm_api_key: str = get_env("LLM_API_KEY", "")

    # 数据库配置
    db_host: str = get_env("DB_HOST", "localhost")
    db_port: str = get_env("DB_PORT", "5432")
    db_name: str = get_env("DB_NAME", "stp")
    db_user: str = get_env("DB_USER", "postgres")
    db_password: str = get_env("DB_PASSWORD", "postgres")
    database_url: str = get_env("POSTGRES_URL", "")

    # 本地存储配置
    local_storage_dir: str = settings_base.local_storage_dir

    # 题目类型配置
    question_types: dict = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "short_answer": "简答题",
        "fill_in_blank": "填空题"
    }

    # 难度级别配置
    difficulty_levels: dict = {
        "easy": "简单",
        "medium": "中等",
        "hard": "困难"
    }

    # 题目模板
    question_template: str = """请基于以下内容生成{num_questions}个题目：

内容：
{content}

题目类型：{question_type}
难度级别：{difficulty}

相关知识点：
{rag_suggestions}

请根据相关知识点来生成题目，确保题目：
1. 覆盖重要的知识点
2. 考察概念之间的关联
3. 难度适中，符合指定的难度级别
4. 选项合理，避免歧义

请生成以下格式的题目：
1. 题目内容
2. 选项（如果是选择题）
3. 正确答案
4. 解析说明

请严格只输出如下JSON格式，不要有任何注释、解释、代码块标记或多余内容，只能输出JSON本体：
{
    "questions": [
        {
            "content": "题目内容",
            "options": ["选项A", "选项B", "选项C", "选项D"],
            "answer": "正确答案",
            "explanation": "解析说明"
        }
    ]
}"""

    # 服务配置
    port: int = settings_base.port

# 创建配置实例
settings = ExtendedQuestionSettings()

# 为了保持向后兼容性，提供与原有全局变量相同名称的变量
STORAGE_MODE = settings.storage_mode
LLM_API_URL = settings.llm_api_url
LLM_MODEL_NAME = settings.llm_model_name
LLM_API_KEY = settings.llm_api_key
DB_HOST = settings.db_host
DB_PORT = settings.db_port
DB_NAME = settings.db_name
DB_USER = settings.db_user
DB_PASSWORD = settings.db_password
DATABASE_URL = settings.database_url
LOCAL_STORAGE_DIR = settings.local_storage_dir
QUESTION_TYPES = settings.question_types
DIFFICULTY_LEVELS = settings.difficulty_levels
QUESTION_TEMPLATE = settings.question_template 