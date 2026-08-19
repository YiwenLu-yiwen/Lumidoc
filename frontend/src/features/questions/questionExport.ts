import type { GeneratedQuestion } from './types';

export type QuestionExportCell = string | number;
export type QuestionExportTable = QuestionExportCell[][];

const FIXED_HEADERS = ['题型', '项目名称', '习题编号', '题干', '答案', '解析'];
const FORMULA_PREFIX = /^[=+\-@\t\r]/;

export function buildQuestionExportTable(
  questions: GeneratedQuestion[],
  projectName: string,
): QuestionExportTable {
  const optionCount = questions.reduce(
    (maximum, question) => Math.max(maximum, question.options?.length ?? 0),
    0,
  );
  const optionHeaders = Array.from(
    { length: optionCount },
    (_, index) => `答案选项(${String.fromCharCode(65 + index)})`,
  );

  return [
    [...FIXED_HEADERS, ...optionHeaders],
    ...questions.map((question, index) => [
      question.type,
      projectName,
      question.id ?? index + 1,
      question.question,
      Array.isArray(question.answer) ? question.answer.join('、') : question.answer,
      question.explanation || '',
      ...Array.from(
        { length: optionCount },
        (_, optionIndex) => question.options?.[optionIndex] ?? '',
      ),
    ]),
  ];
}

export function serializeCsv(table: QuestionExportTable): string {
  return table
    .map((row) =>
      row
        .map((cell) => {
          const value = String(cell);
          const safeValue = FORMULA_PREFIX.test(value) ? `'${value}` : value;
          return `"${safeValue.replace(/"/g, '""')}"`;
        })
        .join(','),
    )
    .join('\r\n');
}

export function sanitizeExportFileName(fileName: string): string {
  const withoutControlCharacters = Array.from(fileName.trim(), (character) =>
    character.charCodeAt(0) < 32 ? '_' : character,
  ).join('');
  const sanitized = withoutControlCharacters
    .replace(/[<>:"/\\|?*]/g, '_')
    .replace(/[. ]+$/g, '')
    .slice(0, 120);
  return sanitized || 'questions';
}
