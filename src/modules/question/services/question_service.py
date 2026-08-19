import json
import os
import asyncpg
from typing import List, Optional
import httpx
from datetime import datetime

from ..config.config import settings
from ..models.question import (
    Question,
    QuestionCreate,
    QuestionUpdate,
    QuestionGenerationRequest,
    QuestionGenerationResponse
)
from src.shared.clients import default_lightrag_client as lightrag_service

class QuestionService:
    def __init__(self):
        self.pool = None
        self.client = httpx.AsyncClient()
        if settings.storage_mode == "local":
            os.makedirs(settings.local_storage_dir, exist_ok=True)

    async def _init_db_pool(self):
        """初始化数据库连接池"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                min_size=5,
                max_size=20
            )
            await self._create_tables()

    async def _create_tables(self):
        """创建数据库表"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    question_type TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    options TEXT[],
                    answer TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    source_content TEXT NOT NULL,
                    project_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    async def _save_to_local(self, questions: List[Question], project_id: str = None):
        """保存题目到本地文件"""
        filename = f"questions_{project_id}.json" if project_id else "questions.json"
        path = os.path.join(settings.local_storage_dir, filename)
        
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                existing_questions = existing.get("questions", [])
            else:
                existing_questions = []
            
            new_questions = [q.dict() for q in questions]
            all_questions = existing_questions + new_questions
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"questions": all_questions}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save questions to local: {str(e)}")

    async def _save_to_database(self, questions: List[Question], project_id: str = None):
        """保存题目到数据库"""
        await self._init_db_pool()
        async with self.pool.acquire() as conn:
            for question in questions:
                await conn.execute('''
                    INSERT INTO questions (
                        content, question_type, difficulty, options,
                        answer, explanation, source_content, project_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ''',
                    question.content,
                    question.question_type,
                    question.difficulty,
                    question.options,
                    question.answer,
                    question.explanation,
                    question.source_content,
                    project_id
                )

    async def _get_rag_suggestions(self, project_id: str, query: str) -> str:
        """使用lightrag_service获取相关建议"""
        try:
            # 使用lightrag_service进行搜索
            suggestions = await lightrag_service.query(project_id, query)
            return suggestions
        except Exception as e:
            print(f"Failed to get RAG suggestions: {str(e)}")
            return ""

    async def generate_questions(self, request: QuestionGenerationRequest, project_id: str = None) -> QuestionGenerationResponse:
        """生成题目"""
        try:
            # 验证题目类型和难度
            if request.question_type not in settings.question_types:
                return QuestionGenerationResponse(
                    questions=[],
                    status="error",
                    message=f"无效的题目类型，可选类型：{list(settings.question_types.keys())}"
                )
            
            if request.difficulty not in settings.difficulty_levels:
                return QuestionGenerationResponse(
                    questions=[],
                    status="error",
                    message=f"无效的难度级别，可选级别：{list(settings.difficulty_levels.keys())}"
                )

            # 使用lightrag_service获取相关建议
            rag_suggestions = await self._get_rag_suggestions(project_id, request.content)
            
            # 构建提示词
            prompt = settings.question_template.format(
                num_questions=request.num_questions,
                content=request.content,
                question_type=settings.question_types[request.question_type],
                difficulty=settings.difficulty_levels[request.difficulty],
                rag_suggestions=rag_suggestions
            )

            # 调用 LLM API
            headers = {
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": settings.llm_model_name,
                "messages": [
                    {"role": "system", "content": "你是一个专业的题目生成助手，请根据要求生成题目。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            }

            response = await self.client.post(
                f"{settings.llm_api_url}/v1",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()

            # 解析响应
            try:
                questions_data = json.loads(result["choices"][0]["message"]["content"])
                questions = []
                
                for q_data in questions_data:
                    question = QuestionCreate(
                        content=q_data["content"],
                        question_type=request.question_type,
                        difficulty=request.difficulty,
                        options=q_data.get("options"),
                        answer=q_data["answer"],
                        explanation=q_data["explanation"],
                        source_content=request.content
                    )
                    questions.append(question)
                
                # 保存题目
                if settings.storage_mode == "database":
                    await self._save_to_database(questions, project_id)
                else:
                    await self._save_to_local(questions, project_id)
                
                return QuestionGenerationResponse(
                    questions=questions,
                    status="success"
                )
            except json.JSONDecodeError:
                return QuestionGenerationResponse(
                    questions=[],
                    status="error",
                    message="无法解析生成的题目"
                )

        except Exception as e:
            return QuestionGenerationResponse(
                questions=[],
                status="error",
                message=str(e)
            )

    async def get_questions(self, project_id: str = None, question_type: str = None, difficulty: str = None) -> List[Question]:
        """获取题目列表"""
        if settings.storage_mode == "database":
            await self._init_db_pool()
            async with self.pool.acquire() as conn:
                query = "SELECT * FROM questions"
                params = []
                conditions = []
                
                if project_id:
                    conditions.append("project_id = $1")
                    params.append(project_id)
                
                if question_type:
                    conditions.append(f"question_type = ${len(params) + 1}")
                    params.append(question_type)
                
                if difficulty:
                    conditions.append(f"difficulty = ${len(params) + 1}")
                    params.append(difficulty)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                rows = await conn.fetch(query, *params)
                return [Question(**row) for row in rows]
        else:
            filename = f"questions_{project_id}.json" if project_id else "questions.json"
            path = os.path.join(settings.local_storage_dir, filename)
            
            if not os.path.exists(path):
                return []
            
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                questions = [Question(**q) for q in data.get("questions", [])]
                
                if question_type:
                    questions = [q for q in questions if q.question_type == question_type]
                
                if difficulty:
                    questions = [q for q in questions if q.difficulty == difficulty]
                
                return questions
            except Exception as e:
                raise Exception(f"Failed to load questions from local: {str(e)}")

    async def update_question(self, question_id: str, question: QuestionUpdate, project_id: str = None) -> Optional[Question]:
        """更新题目"""
        if settings.storage_mode == "database":
            await self._init_db_pool()
            async with self.pool.acquire() as conn:
                query = """
                    UPDATE questions
                    SET content = $1,
                        question_type = $2,
                        difficulty = $3,
                        options = $4,
                        answer = $5,
                        explanation = $6,
                        source_content = $7,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $8
                    RETURNING *
                """
                result = await conn.fetchrow(
                    query,
                    question.content,
                    question.question_type,
                    question.difficulty,
                    question.options,
                    question.answer,
                    question.explanation,
                    question.source_content,
                    question_id
                )
                if result:
                    return Question(**result)
                return None
        else:
            filename = f"questions_{project_id}.json" if project_id else "questions.json"
            path = os.path.join(settings.local_storage_dir, filename)
            
            if not os.path.exists(path):
                return None
            
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                questions = data.get("questions", [])
                for i, q in enumerate(questions):
                    if q["id"] == question_id:
                        for field, value in question.dict(exclude_unset=True).items():
                            questions[i][field] = value
                        questions[i]["updated_at"] = datetime.now().isoformat()
                        
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump({"questions": questions}, f, ensure_ascii=False, indent=2)
                        
                        return Question(**questions[i])
                return None
            except Exception as e:
                raise Exception(f"Failed to update question in local: {str(e)}")

    async def get_question(self, question_id: int) -> Optional[Question]:
        """获取题目"""
        await self._init_db_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT * FROM questions WHERE id = $1
            ''', question_id)
            if row:
                return Question(**row)
            return None

    async def get_question_by_id(self, question_id: str) -> Optional[Question]:
        """通过ID获取题目"""
        if settings.storage_mode == "database":
            await self._init_db_pool()
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, content, type, difficulty, options, answer, explanation, created_at, project_id
                    FROM questions
                    WHERE id = $1
                    """,
                    question_id
                )
                
                if row:
                    return Question(
                        id=row['id'],
                        content=row['content'],
                        type=row['type'],
                        difficulty=row['difficulty'],
                        options=row['options'],
                        answer=row['answer'],
                        explanation=row['explanation'],
                        created_at=row['created_at'],
                        project_id=row['project_id']
                    )
                return None
        else:
            # 从本地文件加载
            # 这里需要遍历所有项目文件查找
            for filename in os.listdir(settings.local_storage_dir):
                if filename.endswith('.json'):
                    with open(os.path.join(settings.local_storage_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for q in data:
                            if q['id'] == question_id:
                                return Question(**q)
            return None

    async def delete_question(self, question_id: str) -> bool:
        """删除题目"""
        if settings.storage_mode == "database":
            await self._init_db_pool()
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM questions
                    WHERE id = $1
                    """,
                    question_id
                )
                
                return "DELETE" in result
        else:
            # 删除本地文件中的题目
            # 这需要遍历所有项目文件
            for filename in os.listdir(settings.local_storage_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(settings.local_storage_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    original_length = len(data)
                    data = [q for q in data if q['id'] != question_id]
                    
                    if len(data) < original_length:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        return True
            
            return False
