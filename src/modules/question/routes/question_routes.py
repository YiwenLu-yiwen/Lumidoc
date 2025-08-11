from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from ..models.question import (
    Question,
    QuestionCreate,
    QuestionUpdate,
    QuestionGenerationRequest,
    QuestionGenerationResponse
)
from ..services.question_service import QuestionService

router = APIRouter(prefix="/questions", tags=["questions"])
question_service = QuestionService()

@router.post("/projects/{project_id}/generate", response_model=QuestionGenerationResponse)
async def generate_questions(project_id: str, request: QuestionGenerationRequest):
    """生成题目"""
    return await question_service.generate_questions(request, project_id)

@router.get("/projects/{project_id}", response_model=None)
async def get_project_questions(
    project_id: str,
    question_type: Optional[str] = Query(None, description="题目类型"),
    difficulty: Optional[str] = Query(None, description="难度级别")
) -> List[Dict[str, Any]]:
    """获取项目题目列表"""
    return await question_service.get_questions(project_id, question_type, difficulty)

@router.get("/projects/{project_id}/{question_id}", response_model=None)
async def get_project_question(project_id: str, question_id: int) -> Dict[str, Any]:
    """获取项目题目"""
    question = await question_service.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    return question

@router.put("/projects/{project_id}/{question_id}", response_model=None)
async def update_project_question(project_id: str, question_id: int, question: QuestionUpdate) -> Dict[str, Any]:
    """更新项目题目"""
    updated_question = await question_service.update_question(question_id, question, project_id)
    if not updated_question:
        raise HTTPException(status_code=404, detail="题目不存在")
    return updated_question

@router.delete("/projects/{project_id}/{question_id}")
async def delete_project_question(project_id: str, question_id: int):
    """删除项目题目"""
    success = await question_service.delete_question(question_id, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"message": "题目已删除"}

@router.get("/", response_model=None)
async def get_all_questions(
    question_type: Optional[str] = Query(None, description="题目类型"),
    difficulty: Optional[str] = Query(None, description="难度级别")
) -> List[Dict[str, Any]]:
    """获取所有题目"""
    return await question_service.get_questions(None, question_type, difficulty)

@router.get("/{question_id}", response_model=None)
async def get_question(question_id: int) -> Dict[str, Any]:
    """获取题目"""
    question = await question_service.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    return question

@router.put("/{question_id}", response_model=None)
async def update_question(question_id: int, question: QuestionUpdate) -> Dict[str, Any]:
    """更新题目"""
    updated_question = await question_service.update_question(question_id, question)
    if not updated_question:
        raise HTTPException(status_code=404, detail="题目不存在")
    return updated_question

@router.delete("/{question_id}")
async def delete_question(question_id: int):
    """删除题目"""
    success = await question_service.delete_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"message": "题目已删除"} 