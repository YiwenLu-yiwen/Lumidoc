from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
from .system_checker import system_checker
from .alert_manager import alert_manager
from src.database import get_db

app = FastAPI()

@app.get("/health")
async def health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """健康检查"""
    try:
        # 运行系统检查
        system_checker.run_all_checks()
        
        # 发送告警测试
        alert_manager.send_alert(
            subject="系统健康检查",
            content="系统运行正常",
            channels=['email']
        )
        
        return {
            "status": "healthy",
            "message": "系统运行正常"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alert")
async def send_alert(
    subject: str,
    content: str,
    channels: list = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """发送告警"""
    try:
        results = alert_manager.send_alert(subject, content, channels)
        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    from config import settings
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.monitoring_service_port) 