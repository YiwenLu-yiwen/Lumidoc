import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import QuestionExporter from './QuestionExporter';
import GuidedQuestionForm from './GuidedQuestionForm';
import type { GeneratedQuestion, GeneratedQuestionsPayload, QuestionStreamEvent } from './types';

const QUESTION_TYPES = [
  { label: '单选题', value: 'single' },
  { label: '多选题', value: 'multiple' },
  { label: '判断题', value: 'truefalse' },
];

export default function QuestionGenerator() {
  const { projectId } = useParams();
  console.log('projectId in QuestionGenerator', projectId);
  const [mode, setMode] = useState<'quick' | 'guided'>('quick');
  const [typeCounts, setTypeCounts] = useState<{ [key: string]: number }>({});
  const [questions, setQuestions] = useState<GeneratedQuestion[]>([]);

  // 题目展示区 mock
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<GeneratedQuestion>>({});

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [graphEmpty, setGraphEmpty] = useState(false);

  const [showAllHistory, setShowAllHistory] = useState(false);
  const [currentQuestions, setCurrentQuestions] = useState<GeneratedQuestion[]>([]);

  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const [filterType, setFilterType] = useState<'all' | 'single' | 'multiple' | 'truefalse'>('all');

  const [showExporter, setShowExporter] = useState(false);
  const [projectName, setProjectName] = useState('');

  // 题型中英文映射
  const typeMap: Record<string, string> = {
    '单选题': 'single',
    '多选题': 'multiple',
    '判断题': 'truefalse',
    'single': 'single',
    'multiple': 'multiple',
    'truefalse': 'truefalse',
  };

  // 提取 fetchHistory
  const fetchHistory = useCallback(async (): Promise<GeneratedQuestion[]> => {
    if (!projectId) return [];
    const res = await fetch(`/api/projects/${projectId}/history_questions`);
    if (res.ok) {
      const data = await res.json() as Partial<GeneratedQuestionsPayload>;
      if (data && data.questions && Array.isArray(data.questions)) {
        // setHistoryQuestions(data.questions);
        // 不自动 setQuestions
        return data.questions;
      }
    }
    return [];
  }, [projectId]);

  // 页面加载时自动读取历史题目
  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // 获取项目名称
  useEffect(() => {
    if (projectId) {
      fetch(`/api/projects/${projectId}`)
        .then(res => res.json())
        .then((data: { name?: string }) => setProjectName(data.name || ''));
    }
  }, [projectId]);

  // 检查知识图谱是否为空
  const checkGraphEmpty = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await fetch(`/api/projects/${projectId}/graph`);
      const data = await res.json();
      setGraphEmpty(!data || !data.nodes || data.nodes.length === 0);
    } catch (error) {
      console.error('Failed to check graph:', error);
      setGraphEmpty(true);
    }
  }, [projectId]);

  // 页面加载时检查知识图谱
  useEffect(() => {
    checkGraphEmpty();
  }, [checkGraphEmpty]);

  // 切换模式
  const handleModeChange = (m: 'quick' | 'guided') => {
    setMode(m);
    setQuestions([]);
  };

  // 生成题目（mock）
  const handleGenerate = async () => {
    if (graphEmpty) {
      alert('知识图谱为空，请先上传文件并生成知识图谱');
      return;
    }
    const totalCount = (typeCounts['single'] || 0) + (typeCounts['multiple'] || 0) + (typeCounts['truefalse'] || 0);
    if (totalCount === 0) {
      alert('请选择出题数量和种类 (当前出题总数为0)');
      return;
    }
    if (totalCount > 50) {
      alert('快速模式下一次最多出50道题');
      return;
    }
    setLoading(true);
    setErrorMsg('');
    const controller = new AbortController();
    setAbortController(controller);
    const randomSeed = Math.floor(Math.random() * 1000000);
    const query = `请出${typeCounts['single'] || 0}道单选题, ${typeCounts['multiple'] || 0}道多选题, ${typeCounts['truefalse'] || 0}道判断题，对于非正确选项应当基于数据库和显示进行产生。选择题的选项请以字符串数组形式输出，每个选项为一个元素，不要用一个字符串拼接所有选项。本次随机种子：${randomSeed}。请严格只输出如下JSON格式，不要有任何注释、解释、代码块标记或多余内容，只能输出JSON本体：{"questions":[{"type":"","question":"","options":["(A)选项A","(B)选项B",...],"answer":"","explanation":""}]}`;

    try {
      const response = await fetch(`/api/projects/${projectId}/generate_questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
        signal: controller.signal,
      });

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法获取响应流');
      }

      let accumulatedText = '';
      let questionsJson: GeneratedQuestionsPayload | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // 将二进制数据转换为文本
        const chunk = new TextDecoder().decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6)) as QuestionStreamEvent;

            if (data.error) {
              throw new Error(data.error);
            }

            if (data.chunk) {
              accumulatedText += data.chunk;
              // 尝试解析完整的JSON
              try {
                const match = accumulatedText.match(/\{[\s\S]*\}/);
                if (match) {
                  questionsJson = JSON.parse(match[0]) as GeneratedQuestionsPayload;
                  if (questionsJson.questions && questionsJson.questions.length > 0) {
                    setQuestions(questionsJson.questions);
                    setCurrentQuestions(questionsJson.questions);
                  }
                }
              } catch {
                // JSON解析失败，继续累积文本
                continue;
              }
            }

            if (data.done) {
              break;
            }
          }
        }
      }

      if (questionsJson && questionsJson.questions && questionsJson.questions.length > 0) {
        setShowAllHistory(false);
        await fetch(`/api/projects/${projectId}/history_questions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(questionsJson),
        });
        setTypeCounts({});
      } else {
        setErrorMsg('AI未生成题目，请检查知识库或参数。');
        setTypeCounts({});
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        setErrorMsg('已终止生成');
      } else {
        setErrorMsg('请求失败: ' + (e instanceof Error ? e.message : String(e)));
      }
      setTypeCounts({});
    } finally {
      setLoading(false);
      setAbortController(null);
    }
  };

  // 取消编辑
  const handleEditCancel = () => {
    setEditingIndex(null);
    setEditForm({});
  };

  // 保存编辑
  const handleEditSave = async (idx: number) => {
    const newQuestions = questions.map((q, i) => i === idx ? { ...q, ...editForm } : q);
    setQuestions(newQuestions);
    setCurrentQuestions(newQuestions);
    // setHistoryQuestions(newQuestions);
    setEditingIndex(null);
    setEditForm({});
    // 同步到后端
    if (projectId) {
      await fetch(`/api/projects/${projectId}/history_questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ questions: newQuestions }),
      });
    }
  };

  // 删除题目
  const handleDelete = async (idx: number) => {
    const newQuestions = questions.filter((_, i) => i !== idx);
    setQuestions(newQuestions);
    setCurrentQuestions(newQuestions);
    // setHistoryQuestions(newQuestions);
    // 同步到后端
    if (projectId) {
      await fetch(`/api/projects/${projectId}/history_questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ questions: newQuestions }),
      });
    }
  };

  // 切换显示模式
  const handleShowAllToggle = async () => {
    setShowAllHistory(v => {
      const next = !v;
      if (next) {
        // 切换到全部历史题目时主动 fetch
        fetchHistory().then(qs => setQuestions(qs));
      } else {
        setQuestions(currentQuestions);
      }
      return next;
    });
  };

  return (
    <div className="max-w-8xl mx-auto py-4 h-screen overflow-y-auto bg-[#181818] text-white">
      <div className="flex justify-center gap-8 mb-8">
        <button
          className={`px-20 py-3 rounded-lg text-lg font-semibold border-2 transition ${mode === 'quick' ? 'bg-blue-500 text-white border-blue-500' : 'bg-[#232325] border-gray-700 text-gray-300 hover:bg-[#232325]'}`}
          onClick={() => handleModeChange('quick')}
        >
          快速模式
        </button>
        <button
          className={`px-20 py-3 rounded-lg text-lg font-semibold border-2 transition ${mode === 'guided' ? 'bg-blue-500 text-white border-blue-500' : 'bg-[#232325] border-gray-700 text-gray-300 hover:bg-[#232325]'}`}
          onClick={() => handleModeChange('guided')}
        >
          引导模式
        </button>
      </div>
      {/* 上：出题配置区 */}
      <div className="mb-4 w-full flex flex-col items-center">
        {mode === 'quick' && (
          <div className="w-full bg-[#232325] border border-gray-700 px-8 py-4 mb-2 rounded-xl">
            <h2 className="text-lg font-bold mb-4 text-white">快速模式</h2>
            <div className="mb-4 flex items-center gap-10">
              <label className="font-semibold text-base w-28 text-gray-300">题目类型及数量</label>
              <div className="flex flex-col gap-3">
                {QUESTION_TYPES.map(t => (
                  <div key={t.value} className="flex items-center gap-4">
                    <span className="w-20 text-gray-300 text-lg font-medium">{t.label}</span>
                    <input
                      type="number"
                      min={0}
                      max={50}
                      value={typeof typeCounts[t.value] === 'number' && typeCounts[t.value] !== 0 ? typeCounts[t.value] : ''}
                      onChange={e => {
                        const val = e.target.value === '' ? 0 : Math.max(0, Number(e.target.value));
                        if (val > 50) {
                          alert('每种题型最多50道题');
                        }
                        setTypeCounts(prev => ({ ...prev, [t.value]: Math.min(val, 50) }));
                      }}
                      className="w-20 px-2 py-1 border border-gray-700 rounded bg-[#181818] text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="数量"
                    />
                  </div>
                ))}
              </div>
            </div>
            <button
              className="mt-2 py-2 px-10 bg-blue-600 text-white rounded-lg font-semibold text-lg hover:bg-blue-700 disabled:opacity-60"
              onClick={loading ? () => { abortController?.abort(); setLoading(false); setAbortController(null); } : handleGenerate}
              disabled={loading && !abortController}
            >
              {loading ? '终止生成' : '生成题目'}
            </button>
          </div>
        )}
        {mode === 'guided' && (
          <div className="w-full bg-[#232325] border border-gray-700 px-8 py-4 flex flex-col items-center justify-center mb-2 rounded-xl">
            <GuidedQuestionForm projectId={projectId || ''} onQuestionsGenerated={(newQuestions) => {
              setShowAllHistory(false);
              setQuestions(newQuestions);
              setCurrentQuestions(newQuestions);
            }} />
          </div>
        )}
      </div>
      {/* 下：题目内容区 */}
      <div className="w-full bg-[#232325] border border-gray-700 px-8 py-4 min-h-[400px] flex flex-col justify-start mb-2 pb-80 rounded-xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white">题目列表</h2>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowExporter(true)}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              输出保存
            </button>
            <span className="mr-3 text-gray-400 text-sm">
              当前：{showAllHistory ? '全部历史题目' : '只看当前题目'}
            </span>
            <button
              className={`ml-4 px-4 py-1 rounded border text-base font-medium transition ${showAllHistory ? 'bg-blue-500 text-white border-blue-500' : 'bg-[#232325] border-gray-700 text-gray-300 hover:bg-[#232325]'}`}
              onClick={handleShowAllToggle}
            >
              {showAllHistory ? '只看当前题目' : '显示全部历史题目'}
            </button>
          </div>
        </div>
        {/* 题型筛选按钮 */}
        <div className="flex gap-2 mb-6">
          <button
            className={`px-4 py-1 rounded ${filterType === 'all' ? 'bg-blue-500 text-white' : 'bg-[#181818] text-gray-300'}`}
            onClick={() => setFilterType('all')}
          >全部</button>
          <button
            className={`px-4 py-1 rounded ${filterType === 'single' ? 'bg-blue-500 text-white' : 'bg-[#181818] text-gray-300'}`}
            onClick={() => setFilterType('single')}
          >单选题</button>
          <button
            className={`px-4 py-1 rounded ${filterType === 'multiple' ? 'bg-blue-500 text-white' : 'bg-[#181818] text-gray-300'}`}
            onClick={() => setFilterType('multiple')}
          >多选题</button>
          <button
            className={`px-4 py-1 rounded ${filterType === 'truefalse' ? 'bg-blue-500 text-white' : 'bg-[#181818] text-gray-300'}`}
            onClick={() => setFilterType('truefalse')}
          >判断题</button>
        </div>
        {errorMsg && <div className="text-red-400 text-lg mb-4">{errorMsg}</div>}
        {questions.length === 0 ? (
          <div className="text-gray-400 text-center py-16 text-lg">暂无题目，请先生成</div>
        ) : (
          <ul className="space-y-8">
            {questions.slice().reverse().filter(q => {
              if (filterType === 'all') return true;
              return typeMap[q.type] === filterType;
            }).map((q, idx) => (
              <li key={idx} className="flex items-start gap-6 text-xl">
                <span className="inline-block w-12 text-gray-500 font-bold">{idx + 1}.</span>
                <div className="flex-1">
                  {editingIndex === idx ? (
                    <div className="space-y-2">
                      <input
                        className="w-full border border-gray-700 rounded px-2 py-1 mb-1 text-lg font-semibold bg-[#181818] text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={editForm.question || ''}
                        onChange={e => setEditForm(f => ({ ...f, question: e.target.value }))}
                      />
                      <div>
                        <span className="text-base font-medium text-gray-300">选项：</span>
                        <ul className="space-y-1">
                          {(editForm.options || []).map((opt: string, i: number) => (
                            <li key={i} className="flex items-center gap-2">
                              <input
                                className="border border-gray-700 rounded px-2 py-1 flex-1 bg-[#181818] text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                value={opt}
                                onChange={e => {
                                  const opts = [...(editForm.options ?? [])];
                                  opts[i] = e.target.value;
                                  setEditForm(f => ({ ...f, options: opts }));
                                }}
                              />
                              <button className="text-red-400" onClick={() => {
                                const opts = [...(editForm.options ?? [])];
                                opts.splice(i, 1);
                                setEditForm(f => ({ ...f, options: opts }));
                              }}>删除</button>
                            </li>
                          ))}
                        </ul>
                        <button className="mt-1 text-blue-400" onClick={() => setEditForm(f => ({ ...f, options: [...(f.options || []), ''] }))}>添加选项</button>
                      </div>
                      <div>
                        <span className="text-base font-medium text-gray-300">答案：</span>
                        <input
                          className="border border-gray-700 rounded px-2 py-1 w-full bg-[#181818] text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          value={Array.isArray(editForm.answer) ? editForm.answer.join('、') : (editForm.answer || '')}
                          onChange={e => setEditForm(f => ({ ...f, answer: e.target.value }))}
                        />
                        <span className="text-gray-500 text-xs ml-2">多个答案用"、"分隔</span>
                      </div>
                      <div>
                        <span className="text-base font-medium text-gray-300">解析：</span>
                        <textarea
                          className="border border-gray-700 rounded px-2 py-1 w-full bg-[#181818] text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          value={editForm.explanation || ''}
                          onChange={e => setEditForm(f => ({ ...f, explanation: e.target.value }))}
                        />
                      </div>
                      <div className="mt-2 flex gap-4">
                        <button className="px-4 py-1 bg-blue-600 text-white rounded" onClick={() => handleEditSave(idx)}>保存</button>
                        <button className="px-4 py-1 bg-gray-700 text-gray-300 rounded" onClick={handleEditCancel}>取消</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="font-semibold mb-2 text-white">{q.question}</div>
                      {Array.isArray(q.options) && q.options.length > 0 && (
                        <ul className="mb-2 pl-4 list-disc text-base text-gray-300">
                          {q.options.map((opt: string, i: number) => (
                            <li key={i}>{opt}</li>
                          ))}
                        </ul>
                      )}
                      <div className="text-base text-green-400 mb-1">答案：{Array.isArray(q.answer) ? q.answer.join('、') : q.answer}</div>
                      <div className="text-base text-gray-400">解析：{q.explanation}</div>
                    </>
                  )}
                </div>
                <button className="ml-4 px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700" onClick={() => handleDelete(questions.length - 1 - idx)}>删除</button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {showExporter && <QuestionExporter questions={questions} projectName={projectName} onClose={() => setShowExporter(false)} />}
    </div>
  );
}
