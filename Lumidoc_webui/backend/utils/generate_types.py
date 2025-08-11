#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# 从main.py导入FastAPI应用
try:
    from Lumidoc_webui.backend.main import app
except ImportError:
    print("Error: 无法导入FastAPI应用，请确保当前目录结构正确")
    sys.exit(1)

def generate_openapi_schema() -> Dict[str, Any]:
    """生成OpenAPI架构"""
    return app.openapi()

def convert_to_typescript(schema: Dict[str, Any], output_dir: str) -> None:
    """将OpenAPI架构转换为TypeScript类型定义"""
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # OpenAPI架构文件路径
    schema_path = os.path.join(output_dir, 'openapi.json')
    
    # 保存OpenAPI架构为JSON文件
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    
    print(f"OpenAPI schema saved to {schema_path}")
    
    # 生成TypeScript类型定义
    try:
        import subprocess
        
        # 使用openapi-typescript工具转换
        # 需要先安装: npm install -g openapi-typescript
        ts_output_path = os.path.join(output_dir, 'api-schema.ts')
        subprocess.run([
            'npx', 'openapi-typescript', 
            schema_path, 
            '--output', ts_output_path
        ], check=True)
        
        print(f"TypeScript definitions generated at {ts_output_path}")
        
    except Exception as e:
        print(f"Error generating TypeScript definitions: {str(e)}")
        print("Please make sure 'openapi-typescript' is installed: npm install -g openapi-typescript")

def main():
    """主函数"""
    # 前端类型定义输出目录
    output_dir = str(Path(__file__).resolve().parent.parent.parent / 'Lumidoc_webui' / 'frontend' / 'src' / 'types')
    
    print("Generating OpenAPI schema...")
    schema = generate_openapi_schema()
    
    print("Converting to TypeScript...")
    convert_to_typescript(schema, output_dir)
    
    print("Done!")

if __name__ == "__main__":
    main() 