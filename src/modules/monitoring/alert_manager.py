import os
from src.shared.logger import initialize_logging, get_logger
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import json
from typing import Optional, Dict
from pathlib import Path
from dotenv import load_dotenv

# 配置日志
initialize_logging("alert_manager")
logger = get_logger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    'email': {
        'smtp_server': None,
        'smtp_port': None,
        'username': None,
        'password': None,
        'receiver': None
    },
    'dingtalk': {
        'webhook': None,
        'secret': None
    },
    'wechat': {
        'webhook': None
    }
}

class AlertManager:
    def __init__(self):
        # 加载环境变量
        env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
        if env_path.exists():
            try:
                load_dotenv(env_path)
                logger.info("成功加载告警配置")
            except Exception as e:
                logger.warning(f"加载告警配置失败: {str(e)}")
        else:
            logger.warning("未找到环境变量配置文件，告警功能将不可用")
        
        # 初始化配置
        self.config = {
            'email': {
                'enabled': bool(os.getenv('SMTP_SERVER')),
                'smtp_server': os.getenv('SMTP_SERVER') or DEFAULT_CONFIG['email']['smtp_server'],
                'smtp_port': int(os.getenv('SMTP_PORT', '0')) or DEFAULT_CONFIG['email']['smtp_port'],
                'username': os.getenv('ALERT_EMAIL') or DEFAULT_CONFIG['email']['username'],
                'password': os.getenv('ALERT_EMAIL_PASSWORD') or DEFAULT_CONFIG['email']['password'],
                'receiver': os.getenv('ALERT_RECEIVER_EMAIL') or DEFAULT_CONFIG['email']['receiver']
            },
            'dingtalk': {
                'enabled': bool(os.getenv('DINGTALK_WEBHOOK')),
                'webhook': os.getenv('DINGTALK_WEBHOOK') or DEFAULT_CONFIG['dingtalk']['webhook'],
                'secret': os.getenv('DINGTALK_SECRET') or DEFAULT_CONFIG['dingtalk']['secret']
            },
            'wechat': {
                'enabled': bool(os.getenv('WECHAT_WEBHOOK')),
                'webhook': os.getenv('WECHAT_WEBHOOK') or DEFAULT_CONFIG['wechat']['webhook']
            }
        }
        
        # 验证配置
        self._validate_config()

    def _validate_config(self):
        """验证告警配置"""
        for channel, config in self.config.items():
            if config['enabled']:
                # 检查该通道的所有必要配置
                missing_configs = []
                for key, value in config.items():
                    if key != 'enabled' and value is None:
                        missing_configs.append(key)
                
                if missing_configs:
                    logger.warning(f"{channel} 告警通道配置不完整，缺少: {', '.join(missing_configs)}")
                    config['enabled'] = False
                else:
                    logger.info(f"{channel} 告警通道已启用")
            else:
                logger.warning(f"{channel} 告警通道未配置")

    def send_email_alert(self, subject: str, content: str) -> bool:
        """发送邮件告警"""
        if not self.config['email']['enabled']:
            logger.warning("邮件告警未配置或配置不完整")
            return False
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config['email']['username']
            msg['To'] = self.config['email']['receiver']
            msg['Subject'] = subject
            
            msg.attach(MIMEText(content, 'plain'))
            
            with smtplib.SMTP(self.config['email']['smtp_server'], self.config['email']['smtp_port']) as server:
                server.starttls()
                server.login(self.config['email']['username'], self.config['email']['password'])
                server.send_message(msg)
                
            logger.info(f"邮件告警发送成功: {subject}")
            return True
        except Exception as e:
            logger.error(f"邮件告警发送失败: {str(e)}")
            return False

    def send_dingtalk_alert(self, content: str) -> bool:
        """发送钉钉告警"""
        if not self.config['dingtalk']['enabled']:
            logger.warning("钉钉告警未配置或配置不完整")
            return False
            
        try:
            headers = {'Content-Type': 'application/json'}
            data = {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
            
            response = requests.post(
                self.config['dingtalk']['webhook'],
                headers=headers,
                data=json.dumps(data)
            )
            
            if response.status_code == 200:
                logger.info("钉钉告警发送成功")
                return True
            else:
                logger.error(f"钉钉告警发送失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"钉钉告警发送失败: {str(e)}")
            return False

    def send_wechat_alert(self, content: str) -> bool:
        """发送企业微信告警"""
        if not self.config['wechat']['enabled']:
            logger.warning("企业微信告警未配置或配置不完整")
            return False
            
        try:
            headers = {'Content-Type': 'application/json'}
            data = {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
            
            response = requests.post(
                self.config['wechat']['webhook'],
                headers=headers,
                data=json.dumps(data)
            )
            
            if response.status_code == 200:
                logger.info("企业微信告警发送成功")
                return True
            else:
                logger.error(f"企业微信告警发送失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"企业微信告警发送失败: {str(e)}")
            return False

    def send_alert(self, subject: str, content: str, channels: Optional[list] = None) -> Dict[str, bool]:
        """发送告警到指定通道"""
        if channels is None:
            channels = ['email', 'dingtalk', 'wechat']
            
        results = {}
        
        if 'email' in channels:
            results['email'] = self.send_email_alert(subject, content)
            
        if 'dingtalk' in channels:
            results['dingtalk'] = self.send_dingtalk_alert(content)
            
        if 'wechat' in channels:
            results['wechat'] = self.send_wechat_alert(content)
            
        return results

# 创建全局告警管理器实例
alert_manager = AlertManager() 