import { useState } from 'react';
import type { GeneratedQuestion } from './types';
import {
  buildQuestionExportTable,
  sanitizeExportFileName,
  serializeCsv,
} from './questionExport';

interface QuestionExporterProps {
  questions: GeneratedQuestion[];
  projectName: string;
  onClose: () => void;
}

export default function QuestionExporter({ questions, projectName, onClose }: QuestionExporterProps) {
  const [selectedQuestions, setSelectedQuestions] = useState<Set<number>>(new Set());
  const [exportFormat, setExportFormat] = useState<'csv' | 'xlsx'>('csv');
  const [fileName, setFileName] = useState(`${projectName}_questions`);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // 处理题目选择
  const handleQuestionSelect = (index: number) => {
    setSelectedQuestions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  // 处理导出
  const handleExport = async () => {
    const selectedQuestionsData = questions.filter((_, index) => selectedQuestions.has(index));
    const table = buildQuestionExportTable(selectedQuestionsData, projectName);
    const safeFileName = sanitizeExportFileName(fileName);

    setExporting(true);
    setExportError(null);
    try {
      if (exportFormat === 'xlsx') {
        const { default: writeExcelFile } = await import('write-excel-file/browser');
        const sheetData = table.map((row, rowIndex) =>
          row.map((value) => ({
            value,
            ...(rowIndex === 0 ? { fontWeight: 'bold' as const } : {}),
          })),
        );
        await writeExcelFile(sheetData, {
          sheet: '题目',
          stickyRowsCount: 1,
        }).toFile(`${safeFileName}.xlsx`);
      } else {
        const blob = new Blob(['\uFEFF', serializeCsv(table)], {
          type: 'text/csv;charset=utf-8',
        });
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `${safeFileName}.csv`;
        link.click();
        URL.revokeObjectURL(downloadUrl);
      }

      onClose();
    } catch (error) {
      setExportError(error instanceof Error ? error.message : '导出失败，请重试');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4 text-gray-800">导出题目</h2>

        {/* 文件格式选择 */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-800 mb-2">文件格式</label>
          <div className="flex gap-4">
            <label className="flex items-center text-gray-800">
              <input
                type="radio"
                value="csv"
                checked={exportFormat === 'csv'}
                onChange={() => setExportFormat('csv')}
                className="mr-2"
              />
              CSV
            </label>
            <label className="flex items-center text-gray-800">
              <input
                type="radio"
                value="xlsx"
                checked={exportFormat === 'xlsx'}
                onChange={() => setExportFormat('xlsx')}
                className="mr-2"
              />
              Excel
            </label>
          </div>
        </div>

        {/* 文件名输入 */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-800 mb-2">文件名</label>
          <input
            type="text"
            value={fileName}
            onChange={(e) => setFileName(e.target.value)}
            className="w-full px-3 py-2 border rounded-md text-gray-700"
          />
        </div>

        {/* 题目选择列表 */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-800 mb-2">选择要导出的题目</label>
          <div className="flex items-center mb-2">
            <input
              type="checkbox"
              id="selectAll"
              checked={selectedQuestions.size === questions.length && questions.length > 0}
              ref={el => {
                if (el) el.indeterminate = selectedQuestions.size > 0 && selectedQuestions.size < questions.length;
              }}
              onChange={e => {
                if (e.target.checked) {
                  setSelectedQuestions(new Set(questions.map((_, idx) => idx)));
                } else {
                  setSelectedQuestions(new Set());
                }
              }}
              className="mr-2"
            />
            <label htmlFor="selectAll" className="text-gray-800 select-none cursor-pointer">
              {selectedQuestions.size === questions.length ? '取消全选' : '全选'}
            </label>
          </div>
          <div className="border rounded-md max-h-60 overflow-y-auto">
            {questions.map((q, index) => (
              <div key={index} className="p-2 border-b last:border-b-0">
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    checked={selectedQuestions.has(index)}
                    onChange={() => handleQuestionSelect(index)}
                    className="mt-1"
                  />
                  <span className="flex-1 text-black">{q.question}</span>
                </label>
              </div>
            ))}
          </div>
        </div>

        {exportError && (
          <p role="alert" className="mb-4 text-sm text-red-600">
            {exportError}
          </p>
        )}

        {/* 操作按钮 */}
        <div className="flex justify-end gap-4">
          <button
            onClick={onClose}
            className="px-4 py-2 border rounded-md hover:bg-gray-50"
          >
            取消
          </button>
          <button
            onClick={handleExport}
            disabled={selectedQuestions.size === 0 || exporting}
            className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
          >
            {exporting ? '正在导出...' : '导出'}
          </button>
        </div>
      </div>
    </div>
  );
}
