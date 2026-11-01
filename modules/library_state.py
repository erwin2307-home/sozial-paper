from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Paper:
    id: str
    title: str = ""
    authors: str = ""
    year: Optional[int] = None
    source: str = "upload"
    abstract: str = ""
    pdf_url: Optional[str] = None
    full_text: Optional[str] = None
    extract_status: str = "pending"
    report: Optional[dict] = None
    mode_used: Optional[str] = None
    pdf_bytes: Optional[bytes] = None
    selected: bool = False


@dataclass
class Library:
    papers: dict = field(default_factory=dict)


def add_paper(library: Library, paper: Paper) -> Library:
    library.papers[paper.id] = paper
    return library


def get_paper(library: Library, paper_id: str) -> Optional[Paper]:
    return library.papers.get(paper_id)


def list_papers(library: Library) -> list:
    return list(library.papers.values())


def remove_paper(library: Library, paper_id: str) -> Library:
    library.papers.pop(paper_id, None)
    return library


def set_report(library: Library, paper_id: str, report: dict, mode_used: str) -> Library:
    paper = library.papers.get(paper_id)
    if paper is not None:
        paper.report = report
        paper.mode_used = mode_used
    return library


def set_full_text(library: Library, paper_id: str, full_text: str, status: str, pdf_bytes: Optional[bytes] = None) -> Library:
    paper = library.papers.get(paper_id)
    if paper is not None:
        paper.full_text = full_text
        paper.extract_status = status
        paper.pdf_bytes = pdf_bytes
    return library


def set_selected(library: Library, paper_id: str, selected: bool) -> Library:
    paper = library.papers.get(paper_id)
    if paper is not None:
        paper.selected = selected
    return library


def usable_text(paper: Paper) -> tuple:
    """Return the best available text and its kind: "full", "abstract" or "none"."""
    if paper.full_text:
        return paper.full_text, "full"
    if paper.abstract:
        return paper.abstract, "abstract"
    return "", "none"
