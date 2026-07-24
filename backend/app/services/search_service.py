"""Real search service: DuckDuckGo HTML + Bing fallback.

Mirrors the search implementation in aitravel-main but uses httpx and the
standard-library html.parser to avoid adding new dependencies.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx


class _ResultExtractor(HTMLParser):
    """Extract search results from DuckDuckGo / Bing HTML pages.

    Usage:
        parser = _ResultExtractor()
        parser.feed(html)
        results = parser.results
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._mode: str | None = None  # 'ddg' | 'bing'
        self._current: dict[str, str] | None = None
        self._field: str | None = None  # 'title' | 'snippet' | None
        self._field_tag: str | None = None
        self._in_h2 = False
        self._in_b_caption = False

    def _container_class(self, attrs: list[tuple[str, str | None]]) -> str | None:
        for name, value in attrs:
            if name == "class" and value:
                classes = value.split()
                if "result" in classes or "web-result" in classes:
                    return "ddg"
                if "b_algo" in classes:
                    return "bing"
        return None

    def _attr(self, attrs: list[tuple[str, str | None]], name: str) -> str | None:
        for n, v in attrs:
            if n == name:
                return v
        return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        container = self._container_class(attrs)
        if container:
            # 每个结果容器都新建一个 current（嵌套/平铺都安全，空壳在清洗时过滤）
            self._mode = container
            self._current = {"title": "", "url": "", "snippet": ""}
            self.results.append(self._current)
            self._field = None
            self._in_h2 = False
            self._in_b_caption = False
            return

        if not self._current:
            return

        cls = self._attr(attrs, "class") or ""
        href = self._attr(attrs, "href") or ""

        if self._mode == "ddg":
            if tag == "a" and "result__a" in cls:
                self._field = "title"
                self._field_tag = "a"
                if href:
                    self._current["url"] = self._unwrap_ddg_url(href)
            elif (tag == "a" or tag == "div") and "result__snippet" in cls:
                self._field = "snippet"
                self._field_tag = tag

        elif self._mode == "bing":
            if tag == "div" and "b_caption" in cls:
                self._in_b_caption = True
            elif tag == "h2":
                self._in_h2 = True
            elif tag == "a" and href and self._in_h2:
                self._field = "title"
                self._field_tag = "a"
                self._current["url"] = href
            elif tag == "p" and self._in_b_caption and not self._in_h2:
                self._field = "snippet"
                self._field_tag = "p"

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self._in_h2 = False
        if tag == "div" and self._in_b_caption:
            self._in_b_caption = False
        if self._field and self._field_tag == tag:
            self._field = None
            self._field_tag = None

    def handle_data(self, data: str) -> None:
        if self._current and self._field:
            self._current[self._field] += data

    def error(self, message: str) -> None:
        # HTMLParser.error is deprecated in newer Python; keep override for safety
        pass

    @staticmethod
    def _unwrap_ddg_url(raw_link: str) -> str:
        if "uddg=" in raw_link:
            parsed = urlparse(raw_link)
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        return raw_link


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


async def _ddg_search(keyword: str, num: int = 10) -> list[dict[str, str]]:
    """Fetch DuckDuckGo HTML results and parse title/url/snippet."""
    url = "https://html.duckduckgo.com/html/"
    params = {"q": keyword}

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        try:
            resp = await client.get(url, params=params, headers=_HEADERS)
            resp.raise_for_status()
        except Exception:
            return []

    parser = _ResultExtractor()
    try:
        parser.feed(resp.text)
    except Exception:
        return []

    cleaned: list[dict[str, str]] = []
    for r in parser.results:
        title = _clean_text(r.get("title", ""))
        url = r.get("url", "").strip()
        snippet = _clean_text(r.get("snippet", ""))
        if title and url:
            cleaned.append({"title": title, "url": url, "snippet": snippet or "（无摘要）"})

    return cleaned[:num]


async def _bing_search(keyword: str, num: int = 10) -> list[dict[str, str]]:
    """Fetch Bing results as fallback."""
    url = "https://www.bing.com/search"
    params = {"q": keyword, "count": str(num), "setlang": "zh-CN"}

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        try:
            resp = await client.get(url, params=params, headers=_HEADERS)
            resp.raise_for_status()
        except Exception as exc:
            return [{"title": "搜索请求失败", "url": "", "snippet": f"网络错误: {exc}"}]

    parser = _ResultExtractor()
    try:
        parser.feed(resp.text)
    except Exception:
        return []

    cleaned: list[dict[str, str]] = []
    for r in parser.results:
        title = _clean_text(r.get("title", ""))
        url = r.get("url", "").strip()
        snippet = _clean_text(r.get("snippet", ""))
        if title and url:
            cleaned.append({"title": title, "url": url, "snippet": snippet or "（无摘要）"})

    if not cleaned:
        cleaned.append({
            "title": "未找到相关结果",
            "url": "",
            "snippet": f"搜索「{keyword}」未返回结果，请尝试更换关键词。",
        })
    return cleaned[:num]


def _clean_text(text: str) -> str:
    """Collapse whitespace and strip HTML entities."""
    text = text.strip().replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text)
    return text


async def web_search(keyword: str, num: int = 10) -> list[dict[str, Any]]:
    """DuckDuckGo first, Bing fallback."""
    if not keyword or not keyword.strip():
        return []
    keyword = keyword.strip()

    results = await _ddg_search(keyword, num=num)
    if len(results) <= 1:
        bing_results = await _bing_search(keyword, num=num)
        if bing_results and not (len(bing_results) == 1 and bing_results[0].get("title") == "搜索请求失败"):
            results = bing_results
        elif not results:
            results = bing_results
    return results
