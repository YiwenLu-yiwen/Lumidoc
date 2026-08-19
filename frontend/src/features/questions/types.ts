export interface GeneratedQuestion {
  id?: string | number;
  type: string;
  question: string;
  options: string[];
  answer: string | string[];
  explanation: string;
}

export interface GeneratedQuestionsPayload {
  questions: GeneratedQuestion[];
}

export interface QuestionStreamEvent {
  chunk?: string;
  done?: boolean;
  error?: string;
}

export interface GuidedQuestionRow {
  type: string;
  brand: string;
  direction: string;
  note: string;
}
