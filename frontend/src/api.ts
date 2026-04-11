import type { ApiErrorResponse, AppError, AskResponse, SystemStatusResponse, UploadResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function normalizeErrorResponse(status: number, payload: unknown): AppError {
  if (payload && typeof payload === "object" && "error" in payload) {
    const errorPayload = payload as ApiErrorResponse;
    return {
      title: errorPayload.error.code,
      detail: errorPayload.error.message,
      hint: errorPayload.error.hint ?? undefined,
    };
  }

  return {
    title: `http_${status}`,
    detail: "The backend returned an unexpected error shape.",
    hint: "Check the backend response body and server logs.",
  };
}

async function parseJsonSafely(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/upload`, {
    method: "POST",
    body: formData,
  });

  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    throw normalizeErrorResponse(response.status, payload);
  }

  return payload as UploadResponse;
}

export async function fetchStatus(): Promise<SystemStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/status`, {
    method: "GET",
  });

  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    throw normalizeErrorResponse(response.status, payload);
  }

  return payload as SystemStatusResponse;
}

export async function askRag(question: string): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/rag/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });

  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    throw normalizeErrorResponse(response.status, payload);
  }

  return payload as AskResponse;
}

export { API_BASE_URL };