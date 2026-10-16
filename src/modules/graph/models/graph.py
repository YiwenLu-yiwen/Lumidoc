from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

class NodeCreate(BaseModel):
    """创建节点请求"""
    label: str
    properties: Optional[Dict[str, Any]] = None
    x: Optional[float] = None
    y: Optional[float] = None
    size: Optional[float] = None
    color: Optional[str] = None

class NodeUpdate(BaseModel):
    """更新节点请求"""
    label: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    x: Optional[float] = None
    y: Optional[float] = None
    size: Optional[float] = None
    color: Optional[str] = None

class EdgeCreate(BaseModel):
    """创建边请求"""
    source: str
    target: str
    label: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    size: Optional[float] = None
    color: Optional[str] = None

class EdgeUpdate(BaseModel):
    """更新边请求"""
    source: Optional[str] = None
    target: Optional[str] = None
    label: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    size: Optional[float] = None
    color: Optional[str] = None

class GraphLayout(BaseModel):
    """图谱布局"""
    type: str = "force"
    config: Optional[Dict[str, Any]] = None
