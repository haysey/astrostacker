"""Scrolling news ticker for astronomy news.

Fetches headlines from astronomy/space RSS feeds and scrolls them
across the bottom of the window while the user waits for processing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List

from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget


# RSS feeds for astronomy and space news
RSS_FEEDS = [
    "https://www.space.com/feeds/all",
    "https://skyandtelescope.org/astronomy-news/feed/",
    "https://spacenews.com/feed/",
]

TICKER_SEPARATOR = "        \u2022        "  # bullet separator


class _FeedFetcher(QObject):
    """Background worker to fetch RSS headlines without blocking the GUI."""

    finished = pyqtSignal(list)  # list[str]

    def run(self):
        headlines: List[str] = []
        for url in RSS_FEEDS:
            try:
                import requests
                resp = requests.get(url, timeout=10, headers={
                    "User-Agent": "HayseysAstrostacker/1.0"
                })
                resp.raise_for_status()
                root = ET.fromstring(resp.content)

                # Standard RSS 2.0: channel/item/title
                for item in root.findall(".//item"):
                    title = item.findtext("title")
                    if title:
                        headlines.append(title.strip())

                # Atom feeds: entry/title
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns):
                    title = entry.findtext("atom:title", namespaces=ns)
                    if title:
                        headlines.append(title.strip())
            except Exception:
                continue

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for h in headlines:
            if h not in seen:
                seen.add(h)
                unique.append(h)

        self.finished.emit(unique[:30])  # cap at 30 headlines


class NewsTicker(QWidget):
    """Scrolling astronomy news ticker bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet(
            "background-color: rgba(0, 0, 0, 0.4);"
            "border-top: 1px solid rgba(255, 255, 255, 0.06);"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._label = QLabel("  Loading astronomy news...")
        self._label.setStyleSheet(
            "color: rgba(255, 149, 0, 0.7);"
            "font-size: 11px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif;"
            "background: transparent;"
            "border: none;"
            "padding: 0px 8px;"
        )
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._label)

        self._full_text = ""
        self._scroll_pos = 0
        self._display_width = 120  # characters visible at once

        # Scroll timer
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._tick)
        self._scroll_timer.setInterval(60)  # ~16fps scrolling

        # Fetch headlines in background thread
        self._fetch_thread = QThread()
        self._fetcher = _FeedFetcher()
        self._fetcher.moveToThread(self._fetch_thread)
        self._fetch_thread.started.connect(self._fetcher.run)
        self._fetcher.finished.connect(self._on_headlines)
        self._fetcher.finished.connect(self._fetch_thread.quit)
        self._fetch_thread.start()

        # Refresh headlines every 15 minutes
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_feeds)
        self._refresh_timer.start(15 * 60 * 1000)

    def _on_headlines(self, headlines: list):
        if not headlines:
            self._label.setText(
                "  No news available — check your internet connection"
            )
            return

        self._full_text = TICKER_SEPARATOR.join(headlines) + TICKER_SEPARATOR
        self._scroll_pos = 0
        self._scroll_timer.start()

    def _tick(self):
        if not self._full_text:
            return

        # Create a window into the scrolling text
        doubled = self._full_text + self._full_text  # seamless loop
        visible = doubled[self._scroll_pos:self._scroll_pos + self._display_width]
        self._label.setText(visible)

        self._scroll_pos += 1
        if self._scroll_pos >= len(self._full_text):
            self._scroll_pos = 0

    def _refresh_feeds(self):
        """Re-fetch headlines periodically."""
        if not self._fetch_thread.isRunning():
            self._fetch_thread = QThread()
            self._fetcher = _FeedFetcher()
            self._fetcher.moveToThread(self._fetch_thread)
            self._fetch_thread.started.connect(self._fetcher.run)
            self._fetcher.finished.connect(self._on_headlines)
            self._fetcher.finished.connect(self._fetch_thread.quit)
            self._fetch_thread.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Adjust visible character count based on widget width
        char_width = 7  # approximate pixel width per character
        self._display_width = max(40, self.width() // char_width)
