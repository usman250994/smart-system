RAG_SYSTEM_PROMPT = """You are a helpful assistant that answers questions strictly from the provided context.
Return response strictly in JSON format:
{
  "answer": "...",
  "confidence": 0-1
}
If the answer cannot be found in the context, respond with:
{
  "answer": "NOT FOUND",
  "confidence": 0.0
}
Do NOT make up information outside the provided context.
"""

RAG_USER_TEMPLATE = """Context:
{context}

Question:
{question}"""
