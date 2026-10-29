from modules.auth import check_password


def test_correct_password_returns_true():
    assert check_password("geheim123", "geheim123") is True


def test_wrong_password_returns_false():
    assert check_password("falsch", "geheim123") is False


def test_empty_entered_returns_false():
    assert check_password("", "geheim123") is False
