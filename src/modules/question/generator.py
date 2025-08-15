from typing import List, Dict, Any, Optional
from src.shared.clients import default_lightrag_client as lightrag_service
from src.shared.clients import default_llm_client as LLMService
from src.modules.graph.services.graph_service import GraphService

class QuestionGenerator:
    def __init__(self, llm_service: LLMService, graph_service: Optional[GraphService] = None):
        self.llm_service = llm_service
        self.graph_service = graph_service
    
    async def generate_questions(self, 
                               context: str, 
                               num_questions: int = 5,
                               project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        生成题目
        
        Args:
            context: 上下文内容
            num_questions: 生成题目数量
            project_id: 项目ID，用于获取图谱数据
            
        Returns:
            List[Dict[str, Any]]: 生成的题目列表
        """
        # 从LightRAG系统获取相关文档
        relevant_docs = await lightrag_service.search(context, project_id=project_id)
        
        # 获取图谱分析结果
        graph_analysis = None
        if self.graph_service and project_id:
            try:
                graph_analysis = await self.graph_service.analyze_graph(project_id)
            except Exception as e:
                print(f"Failed to analyze graph: {e}")
        
        # 构建完整的上下文
        full_context = f"{context}\n\n相关参考：\n" + "\n".join(relevant_docs)
        
        # 添加图谱分析结果到上下文
        if graph_analysis:
            full_context += "\n\n知识图谱分析：\n"
            if graph_analysis["key_nodes"]:
                full_context += "关键概念：\n"
                for node in graph_analysis["key_nodes"]:
                    full_context += f"- {node['label']} (重要性: {node['centrality']:.2f})\n"
            
            if graph_analysis["key_relationships"]:
                full_context += "\n关键关系：\n"
                for rel in graph_analysis["key_relationships"]:
                    full_context += f"- {rel['source']['label']} -> {rel['label']} -> {rel['target']['label']} (强度: {rel['strength']:.2f})\n"
        
        # 构建prompt
        prompt = f"""基于以下内容生成{num_questions}个题目：
{full_context}

请只生成以下类型的题目：
1. 单选题（4个选项）
2. 多选题（4个选项，至少2个正确答案）
3. 判断题

每个题目应该包含：
- 题目内容
- 题目类型
- 正确答案
- 解析说明（必须从原文中找到依据）
- 难度等级（1-3，1最简单）
- 知识点标签

请确保题目：
1. 答案必须能从原文中直接找到依据
2. 难度不要太高，控制在1-2级
3. 选项要清晰明确，避免模棱两可
4. 解析要详细说明答案在原文中的位置
"""
        
        # 使用LLM生成题目
        response = await self.llm_service.process_summary(prompt)
        return self._parse_questions(response)
    
    def _parse_questions(self, response: str) -> List[Dict[str, Any]]:
        """
        解析生成的题目
        
        Args:
            response: LLM响应文本
            
        Returns:
            List[Dict[str, Any]]: 解析后的题目列表
        """
        questions = []
        lines = response.split('\n')
        current_question = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_question:
                    questions.append(current_question)
                    current_question = {}
            elif line.startswith('题目：'):
                current_question['content'] = line[3:].strip()
            elif line.startswith('类型：'):
                current_question['type'] = line[3:].strip()
            elif line.startswith('答案：'):
                current_question['answer'] = line[3:].strip()
            elif line.startswith('解析：'):
                current_question['explanation'] = line[3:].strip()
            elif line.startswith('难度：'):
                current_question['difficulty'] = int(line[3:].strip())
            elif line.startswith('标签：'):
                current_question['tags'] = [tag.strip() for tag in line[3:].split(',')]
        
        if current_question:
            questions.append(current_question)
        
        return questions 