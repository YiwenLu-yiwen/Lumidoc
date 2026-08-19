from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

class LightRAGMode(str, Enum):
    """LightRAG查询模式"""
    SEMANTIC = "semantic"  # 语义搜索
    KEYWORD = "keyword"    # 关键词搜索
    HYBRID = "hybrid"      # 混合搜索

class LightRAGQuery(BaseModel):
    """LightRAG查询请求模型"""
    query: str = Field(..., description="查询内容")
    mode: Optional[LightRAGMode] = Field(None, description="查询模式")
    stream: Optional[bool] = Field(False, description="是否使用流式响应")

class LightRAGDocument(BaseModel):
    """LightRAG文档模型"""
    content: str = Field(..., description="文档内容")
    uri: str = Field(..., description="文档URI")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文档元数据")

class LightRAGResponse(BaseModel):
    """LightRAG查询响应模型"""
    success: bool = Field(True, description="是否成功")
    result: str = Field(..., description="查询结果")
    error: Optional[str] = Field(None, description="错误信息")

class LightRAGBuildRequest(BaseModel):
    """LightRAG构建请求模型"""
    selected_files: List[str] = Field(..., description="选中的文件路径列表")

class LightRAGBuildResponse(BaseModel):
    """LightRAG构建响应模型"""
    success: bool = Field(True, description="是否成功")
    message: str = Field(..., description="构建消息")
    file_count: int = Field(..., description="文件数量")
    error: Optional[str] = Field(None, description="错误信息") 