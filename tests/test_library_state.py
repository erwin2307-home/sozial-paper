from modules.library_state import Paper, Library, add_paper, get_paper, list_papers, remove_paper, set_report, set_full_text

def test_add_and_get_paper():
    lib = Library()
    paper = Paper(id="p1", title="Test Paper")
    add_paper(lib, paper)
    assert get_paper(lib, "p1") is paper

def test_get_missing_paper_returns_none():
    lib = Library()
    assert get_paper(lib, "missing") is None

def test_list_papers_returns_all():
    lib = Library()
    add_paper(lib, Paper(id="p1", title="A"))
    add_paper(lib, Paper(id="p2", title="B"))
    titles = {p.title for p in list_papers(lib)}
    assert titles == {"A", "B"}

def test_remove_paper():
    lib = Library()
    add_paper(lib, Paper(id="p1", title="A"))
    remove_paper(lib, "p1")
    assert get_paper(lib, "p1") is None

def test_set_report_attaches_report_and_mode():
    lib = Library()
    add_paper(lib, Paper(id="p1", title="A"))
    set_report(lib, "p1", {"forschungsfrage": "x"}, "A")
    paper = get_paper(lib, "p1")
    assert paper.report == {"forschungsfrage": "x"}
    assert paper.mode_used == "A"

def test_set_full_text_updates_status():
    lib = Library()
    add_paper(lib, Paper(id="p1", title="A"))
    set_full_text(lib, "p1", "some text", "ok")
    paper = get_paper(lib, "p1")
    assert paper.full_text == "some text"
    assert paper.extract_status == "ok"
