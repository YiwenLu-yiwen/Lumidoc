# 这个文件已被废弃，改为使用共享类型库
# 为了向后兼容，重新导出共享类型

from src.shared.types.response import ApiResponse, ErrorResponse, PaginatedResponse
from src.shared.types.project import (
    ProjectBase, ProjectCreate, ProjectUpdate, ProjectResponse, ProjectStatus
)
from src.shared.types.chat import (
    ChatMessage, ChatSession, ChatRequest, ChatResponse
)
from src.shared.types.file import (
    FileInfo, FileUploadResponse, FileProcessRequest, FileStatus
)
from src.shared.types.graph import (
    GraphNode, GraphEdge, GraphData, GraphAnalysisRequest
)
from src.shared.types.user import (
    UserBase, UserCreate, UserUpdate, UserResponse, 
    UserRole, UserStatus, Token, TokenData
)

# 为保持向后兼容性，继续导出这些类型
# 在未来版本中，应直接从共享类型库导入 