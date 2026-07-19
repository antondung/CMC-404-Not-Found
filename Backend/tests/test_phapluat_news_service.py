from __future__ import annotations

import pytest

from app.services.phapluat_news_service import PhapLuatNewsService, _reader_url


def test_reader_url_does_not_double_scheme() -> None:
    url = "https://phapluat.gov.vn/tin-tuc"
    assert _reader_url(url) == "https://r.jina.ai/https://phapluat.gov.vn/tin-tuc"
    assert "http://https://" not in _reader_url(url)


@pytest.mark.asyncio
async def test_fetch_items_keeps_client_open_for_article_bodies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: article body fetch must run inside the AsyncClient context."""

    class _FakeResp:
        def __init__(self, text: str, status_code: int = 200) -> None:
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError("bad status")

    class _FakeClient:
        closed = False
        calls = 0

        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):
            type(self).closed = False
            return self

        async def __aexit__(self, *args):  # noqa: ANN002
            type(self).closed = True
            return False

        async def get(self, url: str, headers=None):  # noqa: ANN001
            if type(self).closed:
                raise RuntimeError("Cannot send a request, as the client has been closed.")
            type(self).calls += 1
            if "tin-tuc/abc" in url:
                return _FakeResp("Markdown Content:\n\nNoi dung bai viet ve thue doanh nghiep moi.")
            # Listing page with one article link matching topic "thuế"
            listing = (
                '<a href="https://phapluat.gov.vn/tin-tuc/chinh-sach-moi/abc">'
                "Chính phủ điều chỉnh chính sách thuế doanh nghiệp mới 2026"
                "</a>"
            )
            return _FakeResp(listing)

    import app.services.phapluat_news_service as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", _FakeClient)
    items = await PhapLuatNewsService().fetch_items(limit_per_topic=1)
    assert len(items) >= 1
    assert items[0].topic == "thuế"
    assert items[0].body
    assert _FakeClient.calls >= 2
