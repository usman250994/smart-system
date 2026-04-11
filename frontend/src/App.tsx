import { FormEvent, useEffect, useState } from "react";

import { askRag, fetchStatus, uploadPdf } from "./api";
import type { AppError, AskResponse, SystemStatusResponse, UploadResponse } from "./types";

const emptyQuestion = "";

function formatSourcePage(sourcePage: number | null): string {
  if (sourcePage === null || sourcePage === undefined) {
    return "Not available";
  }

  return `Page ${sourcePage + 1}`;
}

function UploadResultBlock({
  systemStatus,
  uploadResult,
}: Readonly<{ systemStatus: SystemStatusResponse | null; uploadResult: UploadResponse | null }>) {
  if (uploadResult) {
    return (
      <>
        <strong>{uploadResult.filename}</strong>
        <p>{uploadResult.chunks_indexed} chunks indexed and ready for retrieval.</p>
      </>
    );
  }

  if (systemStatus?.provider_configured) {
    return <p>No PDF indexed yet.</p>;
  }

  return <p>No PDF indexed yet. Indexing will stay unavailable until the backend API key is configured.</p>;
}

function ResultPanel({
  error,
  answerResult,
}: Readonly<{ error: AppError | null; answerResult: AskResponse | null }>) {
  return (
    <>
      {error ? (
        <div className="error-card" role="alert">
          <p className="error-code">{error.title}</p>
          <h3>{error.detail}</h3>
          {error.hint ? <p>{error.hint}</p> : null}
        </div>
      ) : null}

      {answerResult ? (
        <div className="answer-card">
          <div className="answer-main">
            <p className="answer-label">Answer</p>
            <p className="answer-text">{answerResult.answer}</p>
          </div>
          <div className="metrics">
            <div>
              <span>Confidence</span>
              <strong>{answerResult.confidence.toFixed(2)}</strong>
            </div>
            <div>
              <span>Source</span>
              <strong>{formatSourcePage(answerResult.source_page)}</strong>
            </div>
          </div>
        </div>
      ) : (
        <div className="result-block">
          <p>Answer output appears here after a successful RAG request.</p>
        </div>
      )}
    </>
  );
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [answerResult, setAnswerResult] = useState<AskResponse | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
  const [question, setQuestion] = useState(emptyQuestion);
  const [statusText, setStatusText] = useState("Upload a PDF, then ask a grounded question.");
  const [error, setError] = useState<AppError | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadStatus() {
      try {
        const status = await fetchStatus();
        if (!active) {
          return;
        }
        setSystemStatus(status);
        setStatusText(status.message);
      } catch (error_) {
        if (!active) {
          return;
        }
        setError(error_ as AppError);
      }
    }

    void loadStatus();

    return () => {
      active = false;
    };
  }, []);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setError({
        title: "no_file_selected",
        detail: "Select a PDF before uploading.",
        hint: "Use a local PDF file with text content.",
      });
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadResult(null);
    setAnswerResult(null);
    setStatusText("Uploading and indexing PDF...");

    try {
      const result = await uploadPdf(selectedFile);
      setUploadResult(result);
      setSystemStatus((current) =>
        current
          ? { ...current, indexed_pdf_available: true, message: `Backend is ready. ${result.filename} is indexed.` }
          : current,
      );
      setStatusText(`Indexed ${result.chunks_indexed} chunks from ${result.filename}.`);
    } catch (error_) {
      setError(error_ as AppError);
      setStatusText("Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) {
      setError({
        title: "empty_question",
        detail: "Enter a question before sending it to the backend.",
      });
      return;
    }

    setIsAsking(true);
    setError(null);
    setAnswerResult(null);
    setStatusText("Retrieving relevant chunks and generating answer...");

    try {
      const result = await askRag(question.trim());
      setAnswerResult(result);
      setStatusText("Answer received from the RAG pipeline.");
    } catch (error_) {
      setError(error_ as AppError);
      setStatusText("Question failed.");
    } finally {
      setIsAsking(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <h1>RAG Resume Assistant: Upload, Retrieve, Answer with Sources.</h1>
        <p className="lede">
          Minimal React frontend for your FastAPI RAG backend. Upload a PDF, ask a question, and inspect the
          grounded answer with confidence and source page.
        </p>
        <div className="meta-row">
          <span className="pill">Mode: single document</span>
        </div>
        {systemStatus ? (
          <div className={systemStatus.provider_configured ? "notice success" : "notice warning"}>
            <strong>{systemStatus.provider_configured ? "Backend ready" : "Provider key missing"}</strong>
            <p>{systemStatus.message}</p>
          </div>
        ) : null}
      </section>

      <section className="arch-diagram-section">
        <img
          src="/architecture.png"
          alt="System architecture diagram showing React frontend, FastAPI backend, RAG pipeline, FAISS vector DB and AWS deployment"
          className="arch-diagram"
        />
      </section>

      <section className="grid">
        <article className="panel">
          <div className="panel-head">
            <h2>1. Upload PDF</h2>
            <span>{isUploading ? "working" : "ready"}</span>
          </div>
          <form onSubmit={handleUpload} className="stack">
            <label className="field">
              <span>Choose PDF</span>
              <input
                type="file"
                accept="application/pdf"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <button type="submit" disabled={isUploading}>
              {isUploading ? "Uploading..." : "Upload and Index"}
            </button>
          </form>

          <div className="result-block muted">
            <UploadResultBlock systemStatus={systemStatus} uploadResult={uploadResult} />
          </div>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h2>2. Ask Question</h2>
            <span>{isAsking ? "working" : "ready"}</span>
          </div>
          <form onSubmit={handleAsk} className="stack">
            <label className="field">
              <span>Your question</span>
              <textarea
                rows={5}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask something that should be answerable from the uploaded PDF..."
              />
            </label>
            <button type="submit" disabled={isAsking}>
              {isAsking ? "Asking..." : "Ask RAG API"}
            </button>
          </form>

          {systemStatus && !systemStatus.provider_configured ? (
            <div className="inline-note">
              Live RAG calls are blocked right now because the backend provider key is not configured.
            </div>
          ) : null}
        </article>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <h2>3. Result</h2>
          <span>{statusText}</span>
        </div>
        <ResultPanel error={error} answerResult={answerResult} />
      </section>
    </main>
  );
}