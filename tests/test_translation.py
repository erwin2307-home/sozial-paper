from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from modules import translation


def _google_response(*texts):
    response = Mock(status_code=200)
    response.json.return_value = {"data": {"translations": [{"translatedText": t} for t in texts]}}
    return response


def _gtx_ok(text):
    response = Mock(status_code=200)
    response.json.return_value = [[[text, "original", None, None]], None, "de"]
    return response


def _gtx_blocked():
    return Mock(status_code=429)


def _mymemory(text="", status=200, quota=False):
    response = Mock(status_code=200)
    response.json.return_value = {
        "responseStatus": status, "responseData": {"translatedText": text}, "quotaFinished": quota,
    }
    return response


def _free_get(gtx, mymemory):
    """Route the mocked GET by host, so tests can't pass by call order alone."""
    gtx_iter, mymemory_iter = iter(gtx), iter(mymemory)

    def fake_get(url, **_kwargs):
        return next(gtx_iter if url == translation.GTX_URL else mymemory_iter)

    return fake_get


def test_split_text_keeps_all_content_within_limit():
    text = "\n\n".join(["Absatz eins. " * 30, "Absatz zwei. " * 30, "x" * 1000])
    chunks = translation.split_text(text, limit=500)
    assert all(len(chunk) <= 500 for chunk in chunks)
    assert "".join(chunks).replace("\n", "").replace(" ", "") == text.replace("\n", "").replace(" ", "")


def test_split_text_prefers_paragraph_boundaries():
    assert translation.split_text("Eins.\n\nZwei.", limit=8) == ["Eins.", "Zwei."]


def test_free_uses_google_endpoint_when_it_answers():
    with patch("modules.translation.requests.get", side_effect=_free_get([_gtx_ok("Merhaba")], [])) as mock_get:
        result = translation.translate_text("Hallo", "tr")
    assert result.text == "Merhaba"
    assert result.provider == translation.PROVIDER_GOOGLE_FREE
    assert result.complete is True
    assert mock_get.call_args.kwargs["timeout"] > 0


def test_free_falls_back_to_mymemory_when_google_blocks():
    with patch("modules.translation.requests.get", side_effect=_free_get([_gtx_blocked()], [_mymemory("Merhaba")])):
        result = translation.translate_text("Hallo", "tr")
    assert result == translation.Translation("Merhaba", translation.PROVIDER_MYMEMORY)


def test_free_stops_asking_google_after_first_block():
    text = "Satz eins. " * 200  # needs several MyMemory requests
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        return _gtx_blocked() if url == translation.GTX_URL else _mymemory("Teil")

    with patch("modules.translation.requests.get", side_effect=fake_get):
        translation.translate_text(text, "tr")
    assert calls.count(translation.GTX_URL) == 1
    assert len(calls) > 2


def test_mymemory_chunks_stay_under_its_limit():
    sent = []

    def fake_get(url, **kwargs):
        if url == translation.GTX_URL:
            return _gtx_blocked()
        sent.append(kwargs["params"]["q"])
        return _mymemory("Teil")

    with patch("modules.translation.requests.get", side_effect=fake_get):
        translation.translate_text("Ein Satz. " * 300, "tr")
    assert sent
    assert all(len(q) <= 500 for q in sent)


def test_mymemory_unescapes_html_entities():
    with patch("modules.translation.requests.get",
               side_effect=_free_get([_gtx_blocked()], [_mymemory("L&#39;homme")])):
        assert translation.translate_text("Der Mann", "fr").text == "L'homme"


def test_mymemory_sends_optional_email_only_when_given():
    captured = []

    def fake_get(url, **kwargs):
        if url == translation.GTX_URL:
            return _gtx_blocked()
        captured.append(kwargs["params"])
        return _mymemory("x")

    with patch("modules.translation.requests.get", side_effect=fake_get):
        translation.translate_text("Hallo", "tr")
        translation.translate_text("Hallo", "tr", mymemory_email="ich@example.org")
    assert "de" not in captured[0]
    assert captured[1]["de"] == "ich@example.org"


def test_mymemory_keeps_text_already_in_target_language():
    same = _mymemory("PLEASE SELECT TWO DISTINCT LANGUAGES", status=403)
    with patch("modules.translation.requests.get", side_effect=_free_get([_gtx_blocked()], [same])):
        assert translation.translate_text("Hallo Welt", "de").text == "Hallo Welt"


def test_daily_limit_returns_partial_translation_marked_incomplete():
    text = "Satz eins. " * 100
    replies = [_mymemory("Fertig"), _mymemory("", quota=True)]
    with patch("modules.translation.requests.get", side_effect=_free_get([_gtx_blocked()], replies)):
        result = translation.translate_text(text, "tr")
    assert result.text == "Fertig"
    assert result.complete is False


def test_daily_limit_warning_text_is_not_taken_for_a_translation():
    warning = _mymemory("MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY.")
    with patch("modules.translation.requests.get", side_effect=_free_get([_gtx_blocked()], [warning])):
        with pytest.raises(translation.TranslationError):
            translation.translate_text("Hallo", "tr")


def test_daily_limit_before_any_text_raises_clear_error():
    replies = [_mymemory("", status=429)]
    with patch("modules.translation.requests.get", side_effect=_free_get([_gtx_blocked()], replies)):
        with pytest.raises(translation.TranslationError) as error:
            translation.translate_text("Hallo", "tr")
    assert "Tageslimit" in str(error.value)


def test_network_failure_of_all_free_services_raises_translation_error():
    with patch("modules.translation.requests.get", side_effect=translation.requests.ConnectionError("x")):
        with pytest.raises(translation.TranslationError):
            translation.translate_text("Hallo", "tr")


def test_progress_reaches_completion():
    progress = []
    with patch("modules.translation.requests.get", side_effect=_free_get([_gtx_ok("Merhaba")], [])):
        translation.translate_text("Hallo", "tr", on_progress=progress.append)
    assert progress[-1] == 1.0


def test_google_cloud_sends_key_in_header_not_url():
    with patch("modules.translation.requests.post", return_value=_google_response("Merhaba")) as mock_post:
        result = translation.translate_text("Hallo", "tr", service=translation.SERVICE_GOOGLE_CLOUD, google_key="geheim")
    assert result == translation.Translation("Merhaba", translation.PROVIDER_GOOGLE)
    args, kwargs = mock_post.call_args
    assert "geheim" not in args[0]
    assert "params" not in kwargs
    assert kwargs["headers"]["X-Goog-Api-Key"] == "geheim"
    assert kwargs["json"] == {"q": ["Hallo"], "target": "tr", "format": "text"}
    assert kwargs["timeout"] > 0


def test_google_cloud_joins_chunks_in_order():
    text = "Eins. " * 1000 + "\n\n" + "Zwei. " * 1000
    responses = [_google_response(f"Teil {n}") for n in range(1, 4)]
    with patch("modules.translation.requests.post", side_effect=responses):
        result = translation.translate_text(text, "en", service=translation.SERVICE_GOOGLE_CLOUD, google_key="k")
    assert result.text == "Teil 1\n\nTeil 2\n\nTeil 3"


def test_google_cloud_error_raises_without_leaking_key():
    response = Mock(status_code=403)
    with patch("modules.translation.requests.post", return_value=response):
        with pytest.raises(translation.TranslationError) as error:
            translation.translate_text("Hallo", "tr", service=translation.SERVICE_GOOGLE_CLOUD, google_key="geheim")
    assert "geheim" not in str(error.value)
    assert "403" in str(error.value)


def test_google_cloud_network_error_becomes_translation_error():
    with patch("modules.translation.requests.post", side_effect=translation.requests.ConnectionError("geheim")):
        with pytest.raises(translation.TranslationError) as error:
            translation.translate_text("Hallo", "tr", service=translation.SERVICE_GOOGLE_CLOUD, google_key="geheim")
    assert "geheim" not in str(error.value)


def test_google_cloud_without_key_raises():
    with pytest.raises(translation.TranslationError):
        translation.translate_text("Hallo", "tr", service=translation.SERVICE_GOOGLE_CLOUD)


def test_claude_service_uses_client():
    client = Mock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Merhaba")], stop_reason="end_turn",
    )
    result = translation.translate_text("Hallo", "tr", service=translation.SERVICE_CLAUDE, client=client)
    assert result == translation.Translation("Merhaba", translation.PROVIDER_CLAUDE)
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Türkçe" in prompt
    assert "Hallo" in prompt


def test_claude_service_without_client_raises():
    with pytest.raises(translation.TranslationError):
        translation.translate_text("Hallo", "tr", service=translation.SERVICE_CLAUDE)


def test_too_long_text_is_rejected_before_any_request():
    with patch("modules.translation.requests.get") as mock_get:
        with pytest.raises(translation.TranslationError):
            translation.translate_text("x" * (translation.MAX_CHARS + 1), "tr")
    mock_get.assert_not_called()
