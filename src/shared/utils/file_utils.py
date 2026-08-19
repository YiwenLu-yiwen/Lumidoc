from pathlib import Path
from typing import Union, Tuple

def get_file_extension(filename: Union[str, Path]) -> str:
    """
    获取文件扩展名（小写）
    
    Args:
        filename: 文件名或路径
        
    Returns:
        str: 文件扩展名（包含点，如 .pdf）
    """
    return Path(filename).suffix.lower()

def get_file_type(filename: Union[str, Path]) -> Tuple[str, str]:
    """
    根据文件扩展名判断文件类型
    
    Args:
        filename: 文件名或路径
        
    Returns:
        Tuple[str, str]: (文件类型, MIME类型)
    """
    extension = get_file_extension(filename)
    
    # 文档类型
    if extension in ['.pdf']:
        return 'document', 'application/pdf'
    elif extension in ['.doc', '.docx']:
        return 'document', 'application/msword'
    elif extension in ['.ppt', '.pptx']:
        return 'presentation', 'application/vnd.ms-powerpoint'
    elif extension in ['.xls', '.xlsx']:
        return 'spreadsheet', 'application/vnd.ms-excel'
    elif extension in ['.txt', '.md', '.rst']:
        return 'text', 'text/plain'
    
    # 图像类型
    elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return 'image', f'image/{extension[1:]}'
    
    # 音频类型
    elif extension in ['.mp3', '.wav', '.ogg', '.flac']:
        return 'audio', f'audio/{extension[1:]}'
    
    # 视频类型
    elif extension in ['.mp4', '.avi', '.mov', '.wmv', '.mkv']:
        return 'video', f'video/{extension[1:]}'
    
    # 压缩文件
    elif extension in ['.zip', '.rar', '.7z', '.tar', '.gz']:
        return 'archive', 'application/zip'
    
    # 代码文件
    elif extension in ['.py', '.js', '.java', '.c', '.cpp', '.cs', '.php', '.html', '.css', '.json', '.xml']:
        return 'code', 'text/plain'
    
    # 默认类型
    else:
        return 'unknown', 'application/octet-stream' 