from streamlit.testing.v1 import AppTest

# AppTest.from_file resolves a relative path against the directory of the
# file that calls it (tests/), not against the pytest invocation cwd. Use a
# path relative to this test file to reach the real app.py at the repo root.
APP_PATH = "../app.py"

# app.py transitively imports several heavy third-party packages (anthropic,
# openpyxl, fpdf2, rank_bm25, pypdf). On a cold interpreter that import alone
# can take longer than AppTest's 3s default timeout, failing the very first
# script run with an unrelated RuntimeError. Raise the timeout generously so
# the test genuinely exercises the login gate instead of flaking on import
# cost.
DEFAULT_TIMEOUT = 20


def test_login_wrong_password_shows_error():
    at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
    at.secrets["APP_PASSWORD"] = "geheim123"
    at.run()
    at.text_input[0].input("falsch").run()
    at.button[0].click().run()
    assert any("Falsches Passwort" in e.value for e in at.error)


def test_login_correct_password_reveals_sidebar_nav():
    at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
    at.secrets["APP_PASSWORD"] = "geheim123"
    at.run()
    at.text_input[0].input("geheim123").run()
    at.button[0].click().run()
    assert len(at.sidebar.radio) >= 1
