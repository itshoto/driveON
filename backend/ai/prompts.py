from typing import List

from pydantic import BaseModel, Field


class SummarySchema(BaseModel):
    key_findings: List[str] = Field(description="The document's main findings or conclusions, as short bullet points")
    methodology: str = Field(description="How the document approaches its subject -- research method, structure, etc.")
    dataset: str = Field(default="", description="The dataset(s) used, if any; empty string if not applicable")
    limitations: List[str] = Field(default_factory=list, description="Stated limitations or caveats, if any")
    keywords: List[str] = Field(description="5-10 keywords/topics that describe this document")


SUMMARY_PROMPT = (
    "Read the attached document and summarize it. If it's a research paper, cover findings, "
    "methodology, dataset, and limitations; for other kinds of documents, adapt those fields "
    "sensibly (e.g. methodology can describe how the document is structured, dataset can be "
    "left empty)."
)

CHAT_SYSTEM_PROMPT = (
    "You are driveON's document assistant. Answer questions about the attached PDF(s) "
    "accurately and concisely, naming which document you're referencing whenever the user has "
    "attached more than one. If the answer isn't in the documents, say so plainly rather than "
    "guessing."
)


class SearchResultItem(BaseModel):
    file_id: int
    relevance: str = Field(description="One of: high, medium, low")
    reason: str = Field(description="One short sentence explaining why this file matches the query")


class SearchResults(BaseModel):
    results: List[SearchResultItem]


SEARCH_INSTRUCTIONS_TEMPLATE = (
    "The file listing above belongs to one user of a personal cloud storage app. They're "
    'searching it with this natural-language query:\n\n"{query}"\n\n'
    "Return every file that plausibly matches, ranked by relevance (high/medium/low), each with "
    "a one-sentence reason. Only include files you have a genuine reason to think are relevant "
    "-- an empty list is a fine answer."
)


class CategorizationItem(BaseModel):
    file_id: int
    category: str = Field(description="One of: research, invoices, legal, personal, datasets, reports, other")


class CategorizationBatch(BaseModel):
    categories: List[CategorizationItem]


CATEGORIZE_PROMPT_TEMPLATE = (
    "Classify each of these files into exactly one category: research, invoices, legal, "
    "personal, datasets, reports, or other. Use the filename, file type, and summary (if shown) "
    'to judge. When genuinely unsure, use "other".\n\nFiles:\n{listing}'
)
