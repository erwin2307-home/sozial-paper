from modules.library_state import Library, Paper, add_paper, get_paper, set_full_text, set_selected, usable_text


def test_usable_text_prefers_full_text():
    paper = Paper(id="p1", full_text="Volltext", abstract="Abstract")
    assert usable_text(paper) == ("Volltext", "full")


def test_usable_text_falls_back_to_abstract_when_download_failed():
    paper = Paper(id="p1", full_text="", extract_status="failed", abstract="Abstract")
    assert usable_text(paper) == ("Abstract", "abstract")


def test_usable_text_reports_none_without_any_text():
    assert usable_text(Paper(id="p1")) == ("", "none")


def test_set_selected_marks_paper():
    lib = Library()
    add_paper(lib, Paper(id="p1"))
    set_selected(lib, "p1", True)
    assert get_paper(lib, "p1").selected is True


def test_set_full_text_keeps_pdf_bytes_for_download():
    lib = Library()
    add_paper(lib, Paper(id="p1"))
    set_full_text(lib, "p1", "Text", "ok", pdf_bytes=b"%PDF")
    assert get_paper(lib, "p1").pdf_bytes == b"%PDF"
