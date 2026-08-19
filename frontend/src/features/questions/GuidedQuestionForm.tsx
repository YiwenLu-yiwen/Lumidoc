import { useState, useEffect, useCallback } from "react";
import type {
  GeneratedQuestion,
  GeneratedQuestionsPayload,
  GuidedQuestionRow,
  QuestionStreamEvent
} from './types';

const QUESTION_TYPES = [
  { label: "单选题", value: "single" },
  { label: "多选题", value: "multiple" },
  { label: "判断题", value: "truefalse" },
];

const DIRECTIONS = [
  "产品比较",
  "产品特点",
  "产品卖点",
  "产品优势",
  "产品科技",
  "产品运动场景",
];

interface GuidedQuestionFormProps {
  projectId: string;
  onQuestionsGenerated?: (questions: GeneratedQuestion[]) => void;
}

export default function GuidedQuestionForm({ projectId, onQuestionsGenerated }: GuidedQuestionFormProps) {
  console.log('projectId in GuidedQuestionForm', projectId);
  const [count, setCount] = useState(1);
  const [rows, setRows] = useState<GuidedQuestionRow[]>([]);
  const [brandNames, setBrandNames] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [generatedQuestions, setGeneratedQuestions] = useState<GeneratedQuestion[]>([]);
  const [graphEmpty, setGraphEmpty] = useState(false);

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

  // 获取品牌名
  useEffect(() => {
    if (projectId) {
      const apiUrl = `/api/projects/${projectId}/brand_names`;
      console.log('fetching brand names from', apiUrl);
      fetch(apiUrl)
        .then((res) => res.ok ? res.json() : [])
        .then((data) => setBrandNames(Array.isArray(data) ? data : []));
    }
  }, [projectId]);

  // 自动调整rows数量
  useEffect(() => {
    let safeCount = Number(count);
    if (isNaN(safeCount) || safeCount < 1) safeCount = 1;
    if (safeCount > 10) safeCount = 10;
    setCount(safeCount);
    setRows(prev => {
      if (prev.length === safeCount) return prev;
      if (prev.length < safeCount) {
        return [
          ...prev,
          ...Array.from({ length: safeCount - prev.length }, () => ({
            type: "",
            brand: "",
            direction: "",
            note: "",
          }))
        ];
      } else {
        return prev.slice(0, safeCount);
      }
    });
  }, [count]);

  // 行内容变更
  const handleChange = (idx: number, key: keyof GuidedQuestionRow, value: string) => {
    setRows((prev) =>
      prev.map((row, i) => (i === idx ? { ...row, [key]: value } : row))
    );
  };

  // 生成题目
  const handleGenerate = async () => {
    if (graphEmpty) {
      setErrorMsg('知识图谱为空，请先上传文件并生成知识图谱');
      return;
    }
    setGenerating(true);
    setErrorMsg('');
    const controller = new AbortController();
    setAbortController(controller);
    // 只处理已填写的行
    const validRows = rows.filter(row => row.type && row.brand && row.direction);
    if (validRows.length === 0) {
      setErrorMsg('请至少填写一行完整的题目要求');
      setGenerating(false);
      setAbortController(null);
      return;
    }
    // 拼接prompt，加入随机种子
    const randomSeed = Math.floor(Math.random() * 1000000);
    const prompt = validRows.map((row, idx) => {
      return `请出一道题，题型为【${QUESTION_TYPES.find(t => t.value === row.type)?.label || row.type}】，考察内容为【${row.brand}】，考察方向为【${row.direction}】${row.note ? `，备注：【${row.note}】` : ''}。本题随机种子：${randomSeed + idx}`;
    }).join('\n');
    const finalPrompt = `${prompt}\n请严格只输出如下JSON格式，不要有任何注释、解释、代码块标记或多余内容，只能输出JSON本体：{"questions":[{"type":"","question":"","options":["(A)选项A","(B)选项B",...],"answer":"","explanation":""}]}`;

    try {
      const response = await fetch(`/api/projects/${projectId}/generate_questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: finalPrompt }),
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
                    setGeneratedQuestions(questionsJson.questions);
                    if (onQuestionsGenerated) {
                      onQuestionsGenerated(questionsJson.questions);
                    }
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
        // 写入history_questions.json
        await fetch(`/api/projects/${projectId}/history_questions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(questionsJson),
        });
      } else {
        setErrorMsg('AI未生成题目，请检查输入。');
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        setErrorMsg('已终止生成');
      } else {
        setErrorMsg('请求失败: ' + (e instanceof Error ? e.message : String(e)));
      }
    } finally {
      setGenerating(false);
      setAbortController(null);
    }
  };

  return (
    <div className="text-white">
      <div className="flex items-center gap-4 mb-4">
        <span className="text-white">出题数量：</span>
        <input
          type="number"
          min={1}
          max={10}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
          className="border border-gray-700 px-2 py-1 w-20 bg-transparent text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      {rows.length > 0 && (
        <div className="space-y-4">
          {rows.map((row, idx) => (
            <div key={idx} className="flex gap-4 items-center bg-transparent border border-gray-700 rounded-lg px-4 py-2">
              <select
                className="border border-gray-700 px-2 py-1 bg-transparent text-white text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={row.type}
                onChange={(e) => handleChange(idx, "type", e.target.value)}
              >
                <option value="" className="text-gray-400 bg-[#232325]">题型</option>
                {QUESTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value} className="text-black bg-white">
                    {t.label}
                  </option>
                ))}
              </select>
              <select
                className="border border-gray-700 px-2 py-1 bg-transparent text-white text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={row.brand}
                onChange={(e) => handleChange(idx, "brand", e.target.value)}
              >
                <option value="" className="text-gray-400 bg-[#232325]">考察内容</option>
                {Array.isArray(brandNames) && brandNames.map((name) => (
                  <option key={name} value={name} className="text-black bg-white">
                    {name}
                  </option>
                ))}
              </select>
              <select
                className="border border-gray-700 px-2 py-1 bg-transparent text-white text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={row.direction}
                onChange={(e) => handleChange(idx, "direction", e.target.value)}
              >
                <option value="" className="text-gray-400 bg-[#232325]">考察方向</option>
                {DIRECTIONS.map((d) => (
                  <option key={d} value={d} className="text-black bg-white">
                    {d}
                  </option>
                ))}
              </select>
              <input
                className="border border-gray-700 px-2 py-1 bg-transparent text-white w-96 text-center placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                type="text"
                placeholder="备注（可选）"
                value={row.note}
                onChange={e => handleChange(idx, "note", e.target.value)}
              />
            </div>
          ))}
          <div className="flex justify-start mt-4">
            <button
              className="px-8 py-2 bg-blue-600 text-white rounded-lg font-semibold text-lg hover:bg-blue-700 disabled:opacity-60"
              onClick={generating ? () => { abortController?.abort(); setGenerating(false); setAbortController(null); } : handleGenerate}
              disabled={generating && !abortController}
            >
              {generating ? '终止生成' : '生成题目'}
            </button>
          </div>
          {errorMsg && <div className="text-red-400 text-lg mt-2">{errorMsg}</div>}
          {generatedQuestions.length > 0 && (
            <div className="mt-8">
              <h3 className="text-lg font-bold mb-2 text-white">生成的题目</h3>
              <ul className="space-y-4">
                {generatedQuestions.map((q, i) => (
                  <li key={i} className="bg-transparent border border-gray-700 rounded p-4">
                    <div className="font-semibold mb-2 text-white">{q.question}</div>
                    {Array.isArray(q.options) && q.options.length > 0 && (
                      <ul className="mb-2 pl-4 list-disc text-base text-gray-300">
                        {q.options.map((opt, j) => (
                          <li key={j}>{opt}</li>
                        ))}
                      </ul>
                    )}
                    <div className="text-base text-green-400 mb-1">答案：{Array.isArray(q.answer) ? q.answer.join('、') : q.answer}</div>
                    <div className="text-base text-gray-400">解析：{q.explanation}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
