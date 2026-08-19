from typing import List, Dict, Any, Optional
from datetime import datetime
from src.shared.clients import default_llm_client as LLMService
from src.modules.graph.services.graph_service import GraphService
from .generator import QuestionGenerator
from sqlalchemy.orm import Session
from .models.question import QuestionSet as DBQuestionSet, Question as DBQuestion
import pandas as pd

class QuestionSet:
    def __init__(self, set_id: str):
        self.set_id = set_id
        self.questions: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.metadata: Dict[str, Any] = {
            "difficulty_distribution": {},
            "type_distribution": {},
            "tag_distribution": {}
        }
    
    def add_question(self, question: Dict[str, Any]):
        """添加题目到题集"""
        question_id = f"q_{len(self.questions) + 1}"
        question_data = {
            **question,
            'id': question_id,
            'timestamp': datetime.now()
        }
        
        # 更新元数据
        difficulty = question.get('difficulty', 1)
        self.metadata["difficulty_distribution"][difficulty] = \
            self.metadata["difficulty_distribution"].get(difficulty, 0) + 1
        
        question_type = question.get('type', 'unknown')
        self.metadata["type_distribution"][question_type] = \
            self.metadata["type_distribution"].get(question_type, 0) + 1
        
        for tag in question.get('tags', []):
            self.metadata["tag_distribution"][tag] = \
                self.metadata["tag_distribution"].get(tag, 0) + 1
        
        self.questions.append(question_data)
        self.updated_at = datetime.now()
    
    def remove_question(self, question_id: str) -> bool:
        """删除指定ID的题目"""
        for i, question in enumerate(self.questions):
            if question.get('id') == question_id:
                # 更新元数据
                difficulty = question.get('difficulty', 1)
                self.metadata["difficulty_distribution"][difficulty] = \
                    self.metadata["difficulty_distribution"].get(difficulty, 0) - 1
                if self.metadata["difficulty_distribution"][difficulty] == 0:
                    del self.metadata["difficulty_distribution"][difficulty]
                
                question_type = question.get('type', 'unknown')
                self.metadata["type_distribution"][question_type] = \
                    self.metadata["type_distribution"].get(question_type, 0) - 1
                if self.metadata["type_distribution"][question_type] == 0:
                    del self.metadata["type_distribution"][question_type]
                
                for tag in question.get('tags', []):
                    self.metadata["tag_distribution"][tag] = \
                        self.metadata["tag_distribution"].get(tag, 0) - 1
                    if self.metadata["tag_distribution"][tag] == 0:
                        del self.metadata["tag_distribution"][tag]
                
                # 删除题目
                del self.questions[i]
                self.updated_at = datetime.now()
                return True
        return False
    
    def get_questions(self) -> List[Dict[str, Any]]:
        """获取题集中的所有题目"""
        return self.questions
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取题集元数据"""
        return self.metadata

class QuestionManager:
    def __init__(self, 
                 llm_service: LLMService,
                 graph_service: Optional[GraphService] = None,
                 db: Optional[Session] = None):
        self.llm_service = llm_service
        self.graph_service = graph_service
        self.generator = QuestionGenerator(llm_service, graph_service)
        self.question_sets: Dict[str, QuestionSet] = {}
        self.db = db
    
    def create_question_set(self, set_id: Optional[str] = None) -> str:
        """创建新的题集"""
        if set_id is None:
            set_id = f"set_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if set_id not in self.question_sets:
            self.question_sets[set_id] = QuestionSet(set_id)
            
            # 保存到数据库
            if self.db:
                db_set = DBQuestionSet(id=set_id)
                self.db.add(db_set)
                self.db.commit()
        
        return set_id
    
    async def generate_questions(self, 
                               set_id: str, 
                               context: str, 
                               num_questions: int = 5,
                               question_types: Optional[List[str]] = None,
                               project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        生成题目
        
        Args:
            set_id: 题集ID
            context: 上下文内容
            num_questions: 题目数量
            question_types: 题目类型列表
            project_id: 项目ID，用于获取图谱数据
            
        Returns:
            List[Dict[str, Any]]: 生成的题目列表
        """
        if set_id not in self.question_sets:
            self.create_question_set(set_id)
        
        question_set = self.question_sets[set_id]
        
        # 生成题目
        questions = await self.generator.generate_questions(
            context=context,
            num_questions=num_questions,
            project_id=project_id
        )
        
        # 过滤题目类型
        if question_types:
            questions = [q for q in questions if q.get('type') in question_types]
        
        # 添加到题集
        for question in questions:
            question_set.add_question(question)
            
            # 保存到数据库
            if self.db:
                db_question = DBQuestion(
                    id=question.get('id'),
                    set_id=set_id,
                    type=question.get('type'),
                    difficulty=question.get('difficulty', 1),
                    content=question.get('content'),
                    options=question.get('options', []),
                    answer=question.get('answer'),
                    explanation=question.get('explanation'),
                    tags=question.get('tags', [])
                )
                self.db.add(db_question)
                self.db.commit()
        
        return questions
    
    def get_question_set(self, set_id: str) -> Dict[str, Any]:
        """获取指定题集的题目和元数据"""
        if set_id in self.question_sets:
            question_set = self.question_sets[set_id]
            return {
                "questions": question_set.get_questions(),
                "metadata": question_set.get_metadata()
            }
        
        # 从数据库加载
        if self.db:
            db_set = self.db.query(DBQuestionSet).filter(DBQuestionSet.id == set_id).first()
            if db_set:
                questions = []
                for db_question in db_set.questions:
                    question = {
                        'id': db_question.id,
                        'type': db_question.type,
                        'difficulty': db_question.difficulty,
                        'content': db_question.content,
                        'options': db_question.options,
                        'answer': db_question.answer,
                        'explanation': db_question.explanation,
                        'tags': db_question.tags
                    }
                    questions.append(question)
                
                return {
                    "questions": questions,
                    "metadata": db_set.metadata
                }
        
        return {"questions": [], "metadata": {}}
    
    def remove_question(self, set_id: str, question_id: str) -> bool:
        """删除指定题集中的指定题目"""
        if set_id in self.question_sets:
            success = self.question_sets[set_id].remove_question(question_id)
            if success and self.db:
                # 从数据库删除
                self.db.query(DBQuestion).filter(
                    DBQuestion.id == question_id,
                    DBQuestion.set_id == set_id
                ).delete()
                self.db.commit()
            return success
        
        # 从数据库删除
        if self.db:
            result = self.db.query(DBQuestion).filter(
                DBQuestion.id == question_id,
                DBQuestion.set_id == set_id
            ).delete()
            self.db.commit()
            return result > 0
        
        return False
    
    def clear_question_set(self, set_id: str):
        """清除指定题集"""
        if set_id in self.question_sets:
            del self.question_sets[set_id]
        
        # 从数据库删除
        if self.db:
            self.db.query(DBQuestionSet).filter(DBQuestionSet.id == set_id).delete()
            self.db.commit()
    
    def clear_all_question_sets(self):
        """清除所有题集"""
        self.question_sets.clear()
        
        # 从数据库删除
        if self.db:
            self.db.query(DBQuestionSet).delete()
            self.db.commit()
    
    def export_question_set(self, set_id: str, format: str = 'json') -> str:
        """
        导出题集
        
        Args:
            set_id: 题集ID
            format: 导出格式（json/markdown/excel）
            
        Returns:
            str: 导出的内容
        """
        if set_id not in self.question_sets:
            return ""
        
        question_set = self.question_sets[set_id]
        questions = question_set.get_questions()
        metadata = question_set.get_metadata()
        
        if format == 'json':
            import json
            return json.dumps({
                "questions": questions,
                "metadata": metadata
            }, ensure_ascii=False, indent=2)
        elif format == 'markdown':
            markdown = []
            
            # 添加元数据
            markdown.append("## 题集统计")
            markdown.append(f"- 题目总数：{len(questions)}")
            markdown.append("\n### 难度分布")
            for diff, count in metadata["difficulty_distribution"].items():
                markdown.append(f"- 难度{diff}：{count}题")
            markdown.append("\n### 类型分布")
            for qtype, count in metadata["type_distribution"].items():
                markdown.append(f"- {qtype}：{count}题")
            markdown.append("\n### 知识点分布")
            for tag, count in metadata["tag_distribution"].items():
                markdown.append(f"- {tag}：{count}题")
            
            # 添加题目
            markdown.append("\n## 题目列表")
            for i, q in enumerate(questions, 1):
                markdown.append(f"\n### 题目 {i}")
                markdown.append(f"**类型：** {q.get('type', '未知')}")
                markdown.append(f"**难度：** {q.get('difficulty', 1)}")
                markdown.append(f"**标签：** {', '.join(q.get('tags', []))}")
                markdown.append(f"\n{q['content']}\n")
                
                # 根据题目类型显示选项
                if q.get('type') in ['单选题', '多选题']:
                    markdown.append("**选项：**")
                    for opt in q.get('options', []):
                        markdown.append(f"- {opt}")
                
                markdown.append(f"**答案：** {q['answer']}\n")
                markdown.append(f"**解析：** {q['explanation']}\n")
                markdown.append("---")
            
            return "\n".join(markdown)
        elif format == 'excel':
            # 准备Excel数据
            excel_data = []
            for q in questions:
                row = {
                    '题目ID': q.get('id', ''),
                    '题目类型': q.get('type', ''),
                    '难度': q.get('difficulty', 1),
                    '知识点标签': ', '.join(q.get('tags', [])),
                    '题目内容': q.get('content', ''),
                    '选项A': q.get('options', [''])[0] if q.get('type') in ['单选题', '多选题'] else '',
                    '选项B': q.get('options', [''])[1] if q.get('type') in ['单选题', '多选题'] else '',
                    '选项C': q.get('options', [''])[2] if q.get('type') in ['单选题', '多选题'] else '',
                    '选项D': q.get('options', [''])[3] if q.get('type') in ['单选题', '多选题'] else '',
                    '正确答案': q.get('answer', ''),
                    '解析': q.get('explanation', '')
                }
                excel_data.append(row)
            
            # 创建DataFrame
            df = pd.DataFrame(excel_data)
            
            # 将DataFrame转换为Excel格式的字节流
            import io
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='题目列表')
                
                # 添加统计信息
                stats_data = []
                stats_data.append(['题目总数', len(questions)])
                stats_data.append(['难度分布'])
                for diff, count in metadata["difficulty_distribution"].items():
                    stats_data.append([f'难度{diff}', count])
                stats_data.append(['类型分布'])
                for qtype, count in metadata["type_distribution"].items():
                    stats_data.append([qtype, count])
                stats_data.append(['知识点分布'])
                for tag, count in metadata["tag_distribution"].items():
                    stats_data.append([tag, count])
                
                pd.DataFrame(stats_data).to_excel(writer, index=False, header=False, sheet_name='统计信息')
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}") 