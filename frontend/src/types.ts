export type UploadResponse = {
  filename: string;
  chunks_indexed: number;
};

export type SystemStatusResponse = {
  provider_configured: boolean;
  indexed_pdf_available: boolean;
  message: string;
};

export type AskResponse = {
  answer: string;
  confidence: number;
  source_page: number | null;
  source_snippet: string | null;
};

export type ApiErrorResponse = {
  error: {
    code: string;
    message: string;
    hint?: string | null;
  };
};

export type AppError = {
  title: string;
  detail: string;
  hint?: string;
};