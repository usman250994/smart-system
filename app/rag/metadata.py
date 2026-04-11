"""Utilities for extracting metadata from LangChain document objects."""


def get_page_number(doc) -> int | None:
    """Extract page number from document metadata. Returns None if not found."""
    if hasattr(doc, "metadata") and isinstance(doc.metadata, dict):
        return doc.metadata.get("page")
    return None


def get_all_page_numbers(docs: list) -> list[int]:
    """Extract and deduplicate page numbers from a list of documents."""
    pages = set()
    for doc in docs:
        page = get_page_number(doc)
        if page is not None:
            pages.add(page)
    return sorted(pages)
