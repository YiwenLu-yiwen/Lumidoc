import { describe, expect, it } from 'vitest';

import {
  buildQuestionExportTable,
  sanitizeExportFileName,
  serializeCsv,
} from '../../src/features/questions/questionExport';


describe('question export', () => {
  it('builds columns for every answer option', () => {
    const table = buildQuestionExportTable(
      [
        {
          id: 'q-1',
          type: '单选题',
          question: 'Which one?',
          options: ['A1', 'B1', 'C1'],
          answer: 'A',
          explanation: 'Because.',
        },
      ],
      'Demo',
    );

    expect(table[0]).toContain('答案选项(C)');
    expect(table[1]).toContain('C1');
  });

  it('neutralizes spreadsheet formulas in CSV output', () => {
    const csv = serializeCsv([['题干'], ['=HYPERLINK("https://example.test")']]);

    expect(csv).toContain("'=HYPERLINK");
    expect(csv).not.toContain('\n"=HYPERLINK');
  });

  it('removes path separators and reserved filename characters', () => {
    expect(sanitizeExportFileName('../bad:name')).toBe('.._bad_name');
  });
});
