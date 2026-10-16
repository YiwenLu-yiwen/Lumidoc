from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from typing import Optional, List
import redis
import os
from .question_manager import QuestionManager
from src.modules.llm_chat import LLMToolService
from src.modules.graph.services.graph_service import GraphService
from sqlalchemy.orm import Session
from src.database import get_db
import json
from pathlib import Path
from .config.config import settings

app = FastAPI(title="Question Generator Service")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化服务
llm_service = LLMToolService()
graph_service = GraphService()

# 初始化Redis连接
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=6379,
    db=0
)

class GenerateQuestionsRequest(BaseModel):
    set_id: Optional[str] = None
    context: str
    num_questions: int = 5
    question_types: Optional[List[str]] = None
    project_id: Optional[str] = None

def get_question_manager(db: Session = Depends(get_db)) -> QuestionManager:
    """获取题目管理器实例"""
    return QuestionManager(llm_service, graph_service, db)

@app.post("/generate")
async def generate_questions(request: GenerateQuestionsRequest, question_manager: QuestionManager = Depends(get_question_manager)):
    """生成题目"""
    try:
        # 如果没有set_id，创建一个新的题集
        if not request.set_id:
            request.set_id = question_manager.create_question_set()
        
        # 生成题目
        questions = await question_manager.generate_questions(
            set_id=request.set_id,
            context=request.context,
            num_questions=request.num_questions,
            question_types=request.question_types,
            project_id=request.project_id
        )
        
        return {
            "status": "success",
            "set_id": request.set_id,
            "questions": questions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/questions/{set_id}")
async def get_questions(set_id: str, question_manager: QuestionManager = Depends(get_question_manager)):
    """获取题集中的题目和元数据"""
    try:
        result = question_manager.get_question_set(set_id)
        return {
            "status": "success",
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/question/{set_id}/{question_id}")
async def delete_question(set_id: str, question_id: str, question_manager: QuestionManager = Depends(get_question_manager)):
    """删除指定题集中的指定题目"""
    try:
        success = question_manager.remove_question(set_id, question_id)
        if not success:
            raise HTTPException(status_code=404, detail="Question not found")
        return {
            "status": "success",
            "message": f"Question {question_id} deleted from set {set_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/export/{set_id}")
async def export_questions(set_id: str, format: str = "json", question_manager: QuestionManager = Depends(get_question_manager)):
    """导出题集"""
    try:
        content = question_manager.export_question_set(set_id, format)
        if format == "excel":
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=questions_{set_id}.xlsx"
                }
            )
        return {
            "status": "success",
            "format": format,
            "content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/set/{set_id}")
async def clear_question_set(set_id: str, question_manager: QuestionManager = Depends(get_question_manager)):
    """清除题集"""
    try:
        question_manager.clear_question_set(set_id)
        return {
            "status": "success",
            "message": f"Question set {set_id} cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 添加历史问题相关功能
@app.post("/projects/{project_id}/history_questions")
async def save_history_questions(project_id: str, questions: dict, db: Session = Depends(get_db)):
    """保存历史问题"""
    try:
        project_dir = Path(f"projects/{project_id}")
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "history_questions.json"
        
        # 读取原有问题
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                old = json.load(f)
            old_questions = old.get("questions", [])
        else:
            old_questions = []
            
        # 追加新问题
        new_questions = questions.get("questions", [])
        all_questions = old_questions + new_questions
        
        # 保存到文件
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"questions": all_questions}, f, ensure_ascii=False, indent=2)
            
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/projects/{project_id}/history_questions")
async def get_history_questions(project_id: str, db: Session = Depends(get_db)):
    """获取历史问题"""
    try:
        path = Path(f"projects/{project_id}/history_questions.json")
        if not path.exists():
            return {"questions": []}
            
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/projects/{project_id}/info")
async def get_project_info(project_id: str, db: Session = Depends(get_db)):
    """获取项目信息"""
    try:
        path = Path("data/projects.json")
        if not path.exists():
            raise HTTPException(status_code=404, detail="projects.json not found")
            
        with open(path, "r", encoding="utf-8") as f:
            projects = json.load(f)
            
        for proj in projects:
            if proj.get("id") == project_id:
                return {"id": proj["id"], "name": proj["name"]}
                
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port) 