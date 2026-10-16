"""检索模式必须跳过答案生成与答案后处理。"""
from unittest.mock import AsyncMock, Mock
import pytest
from src.modules.lightraglocal.services.enterprise_lightrag_service import EnterpriseLightRAGService

@pytest.mark.asyncio
async def test_context_only_is_passed_to_lightrag():
    service = EnterpriseLightRAGService.__new__(EnterpriseLightRAGService)
    rag = Mock()
    rag.aquery = AsyncMock(return_value='招聘.txt: 职位是软件工程师')
    service._get_project_rag = AsyncMock(return_value=rag)
    service._postprocess_query_result = Mock(side_effect=AssertionError('上下文不能做答案后处理'))
    result = await service.query_project('project', '职位是什么？', mode='naive', only_need_context=True)
    assert result['success'] is True
    assert result['result'] == '招聘.txt: 职位是软件工程师'
    assert rag.aquery.call_args.args[1].only_need_context is True

@pytest.mark.asyncio
async def test_query_limits_retrieval_and_answer_generation():
    service = EnterpriseLightRAGService.__new__(EnterpriseLightRAGService)
    rag = Mock()
    rag.aquery = AsyncMock(return_value='A concise answer')
    rag.llm_model_func = AsyncMock(return_value='A concise answer')
    service._get_project_rag = AsyncMock(return_value=rag)
    service._postprocess_query_result = Mock(return_value='A concise answer')
    result = await service.query_project('project', 'question', mode='hybrid', top_k=5)
    assert result['success']
    param = rag.aquery.call_args.args[1]
    assert param.top_k == 5
    assert param.chunk_top_k == 5
    assert param.max_total_tokens == 4096
    await param.model_func('prompt')
    assert rag.llm_model_func.call_args.kwargs['max_tokens'] == 384
