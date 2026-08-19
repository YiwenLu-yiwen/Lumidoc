from typing import TypeVar, Type, Dict, Any, List, Union, Optional
from pydantic import BaseModel
from datetime import datetime

T = TypeVar('T', bound=BaseModel)

def to_response_model(model_class: Type[T], data: Union[Dict[str, Any], List[Dict[str, Any]], BaseModel, None]) -> Optional[Union[T, List[T]]]:
    """
    将数据转换为指定的响应模型类型
    
    Args:
        model_class: Pydantic模型类
        data: 要转换的数据，可以是字典、列表、BaseModel或None
        
    Returns:
        转换后的模型实例或列表
    """
    if data is None:
        return None
        
    # 处理列表数据
    if isinstance(data, list):
        return [to_response_model(model_class, item) for item in data]
    
    # 处理BaseModel数据
    if isinstance(data, BaseModel):
        # 如果数据已经是目标类型，直接返回
        if isinstance(data, model_class):
            return data
        # 否则转换为字典再处理
        data = data.dict()
    
    # 处理字典数据
    if isinstance(data, dict):
        # 创建模型实例
        try:
            return model_class(**data)
        except Exception as e:
            print(f"Error converting to {model_class.__name__}: {str(e)}")
            # 尝试进行字段类型修正
            fixed_data = _fix_date_fields(data)
            return model_class(**fixed_data)
    
    # 不支持的数据类型
    raise ValueError(f"Unsupported data type: {type(data)}")

def _fix_date_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    修复字典中的日期字段，确保datetime和date类型的兼容性
    
    Args:
        data: 原始数据字典
        
    Returns:
        修复后的数据字典
    """
    result = {}
    
    for key, value in data.items():
        # 处理嵌套字典
        if isinstance(value, dict):
            result[key] = _fix_date_fields(value)
        # 处理嵌套列表
        elif isinstance(value, list):
            result[key] = [
                _fix_date_fields(item) if isinstance(item, dict) else item
                for item in value
            ]
        # 处理日期字符串转换
        elif isinstance(value, str) and _looks_like_iso_date(value):
            try:
                # 尝试转换为datetime
                result[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                # 如果失败，保留原始值
                result[key] = value
        else:
            result[key] = value
            
    return result

def _looks_like_iso_date(value: str) -> bool:
    """
    检查字符串是否看起来像ISO日期格式
    
    Args:
        value: 要检查的字符串
        
    Returns:
        是否可能是日期字符串
    """
    if not isinstance(value, str):
        return False
        
    # 简单检查是否符合ISO日期格式的特征
    if len(value) < 10:
        return False
        
    date_parts = value[:10].split('-')
    if len(date_parts) != 3:
        return False
        
    try:
        year, month, day = map(int, date_parts)
        return 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31
    except ValueError:
        return False 