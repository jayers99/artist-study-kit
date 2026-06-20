from types import SimpleNamespace

import pytest

from scripts.firecrawl_fetch import FetchedPage, fetch_page, normalize_scrape


def _resp(markdown="# Title\n\nBody", **meta):
    md = {"sourceURL": "https://example.com", "url": "https://example.com", "statusCode": 200}
    md.update(meta)
    return SimpleNamespace(markdown=markdown, metadata=md)


def test_normalize_reads_markdown_and_metadata():
    page = normalize_scrape("https://example.com", _resp())
    assert isinstance(page, FetchedPage)
    assert page.markdown.startswith("# Title")
    assert page.status_code == 200
    assert page.final_url == "https://example.com"


def test_normalize_prefers_final_url_after_redirect():
    page = normalize_scrape(
        "https://example.com/old",
        _resp(url="https://example.com/new", sourceURL="https://example.com/old"),
    )
    assert page.url == "https://example.com/old"
    assert page.final_url == "https://example.com/new"


def test_normalize_tolerates_data_wrapper():
    wrapped = SimpleNamespace(data=_resp(markdown="wrapped"))
    page = normalize_scrape("https://example.com", wrapped)
    assert page.markdown == "wrapped"


def test_normalize_defaults_when_metadata_missing():
    page = normalize_scrape("https://example.com", SimpleNamespace(markdown="x"))
    assert page.metadata == {}
    assert page.status_code == 0
    assert page.final_url == "https://example.com"


def test_normalize_coerces_pydantic_metadata_with_snake_case_keys():
    # firecrawl-py v4 returns a DocumentMetadata model (not a dict) with snake_case keys.
    class DocumentMetadata:
        def model_dump(self):
            return {
                "url": "https://example.com/x",
                "source_url": "https://example.com/x",
                "status_code": 200,
            }

    resp = SimpleNamespace(markdown="# Klee", metadata=DocumentMetadata())
    page = normalize_scrape("https://example.com/x", resp)
    assert page.status_code == 200
    assert page.final_url == "https://example.com/x"
    assert page.metadata["status_code"] == 200


def test_fetch_page_uses_injected_client():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def scrape(self, url):
            self.calls.append(url)
            return _resp(markdown=f"scraped {url}")

    client = FakeClient()
    page = fetch_page("https://example.com", client=client)
    assert client.calls == ["https://example.com"]
    assert page.markdown == "scraped https://example.com"


def test_fetch_page_without_client_and_without_key_raises():
    import os

    saved = os.environ.pop("FIRECRAWL_API_KEY", None)
    try:
        with pytest.raises(KeyError):
            fetch_page("https://example.com")
    finally:
        if saved is not None:
            os.environ["FIRECRAWL_API_KEY"] = saved
