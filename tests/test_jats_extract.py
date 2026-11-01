from modules import jats_extract

ARTICLE = (
    b'<?xml version="1.0"?><!DOCTYPE article PUBLIC "-//NLM//DTD JATS//EN" "JATS.dtd">'
    b"<article><front><article-title>Vorspann</article-title></front><body>"
    b"<sec><title>Einleitung</title><p>Erster <italic>Absatz</italic>.</p>"
    b"<sec><title>Teil</title><p>Zweiter Absatz.</p></sec></sec>"
    b"</body><back><ref-list><p>Referenz</p></ref-list></back></article>"
)


def test_is_jats_xml_detects_xml_but_not_pdf():
    assert jats_extract.is_jats_xml(b"\n<!DOCTYPE article><article/>")
    assert not jats_extract.is_jats_xml(b"%PDF-1.7")


def test_extract_text_reads_body_in_document_order_only():
    text, status = jats_extract.extract_text(ARTICLE)
    assert status == "ok"
    assert text == "Einleitung\n\nErster Absatz.\n\nTeil\n\nZweiter Absatz."


def test_extract_text_fails_without_body():
    assert jats_extract.extract_text(b"<article><front/></article>") == ("", "failed")


def test_extract_text_fails_on_broken_xml():
    assert jats_extract.extract_text(b"<article><body>") == ("", "failed")


def test_extract_text_rejects_entity_expansion():
    bomb = b'<!DOCTYPE a [<!ENTITY x "y">]><article><body><p>&x;</p></body></article>'
    assert jats_extract.extract_text(bomb) == ("", "failed")
