"""Scrolling news ticker for astronomy news.

Fetches headlines from astronomy/space RSS feeds and scrolls them
across the bottom of the window while the user waits for processing.

Each headline is clickable — opens the original article in the browser.
"""

from __future__ import annotations

import webbrowser
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List

from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


# RSS feeds for astronomy and space news
RSS_FEEDS = [
    "https://www.space.com/feeds/all",
    "https://skyandtelescope.org/astronomy-news/feed/",
    "https://spacenews.com/feed/",
]

TICKER_SEPARATOR = "        \u2022        "  # bullet separator


@dataclass
class HeadlineItem:
    """A news headline with its source URL."""
    title: str
    url: str


class _FeedFetcher(QObject):
    """Background worker to fetch RSS headlines without blocking the GUI."""

    finished = pyqtSignal(list)  # list[HeadlineItem]

    def run(self):
        items: List[HeadlineItem] = []
        for feed_url in RSS_FEEDS:
            try:
                import requests
                resp = requests.get(feed_url, timeout=10, headers={
                    "User-Agent": "HayseysAstrostacker/1.0"
                })
                resp.raise_for_status()
                root = ET.fromstring(resp.content)

                # Standard RSS 2.0: channel/item
                for item in root.findall(".//item"):
                    title = item.findtext("title")
                    link = item.findtext("link")
                    if title and link:
                        items.append(HeadlineItem(
                            title=title.strip(), url=link.strip()
                        ))

                # Atom feeds: entry
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns):
                    title = entry.findtext("atom:title", namespaces=ns)
                    link_el = entry.find("atom:link[@rel='alternate']", ns)
                    if link_el is None:
                        link_el = entry.find("atom:link", ns)
                    link = link_el.get("href") if link_el is not None else None
                    if title and link:
                        items.append(HeadlineItem(
                            title=title.strip(), url=link.strip()
                        ))
            except Exception:
                continue

        # Deduplicate by title while preserving order
        seen = set()
        unique = []
        for item in items:
            if item.title not in seen:
                seen.add(item.title)
                unique.append(item)

        self.finished.emit(unique[:30])  # cap at 30 headlines


class NewsTicker(QWidget):
    """Scrolling astronomy news ticker bar.

    Click anywhere on the ticker to open the currently visible
    headline's article in your default web browser.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("Click to open this story in your browser")
        self.setStyleSheet(
            "background-color: rgba(0, 0, 0, 0.4);"
            "border-top: 1px solid rgba(255, 255, 255, 0.06);"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._label = QLabel("  Loading astronomy news...")
        self._label.setStyleSheet(
            "color: rgba(255, 149, 0, 0.8);"
            "font-size: 13px;"
            "font-weight: 700;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif;"
            "background: transparent;"
            "border: none;"
            "padding: 0px 8px;"
        )
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._label)

        self._headlines: List[HeadlineItem] = []
        self._full_text = ""
        self._scroll_pos = 0
        self._display_width = 120  # characters visible at once

        # Track which headline index is currently centred on screen
        self._headline_offsets: List[int] = []  # char offset where each headline starts

        # Scroll timer
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._tick)
        self._scroll_timer.setInterval(80)  # smooth scrolling, ~30% slower

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

    def _on_headlines(self, items: list):
        if not items:
            self._label.setText(
                "  No news available \u2014 check your internet connection"
            )
            return

        self._headlines = items

        # Build the full scrolling text and record where each headline starts
        self._headline_offsets = []
        parts = []
        offset = 0
        for item in items:
            self._headline_offsets.append(offset)
            part = item.title + TICKER_SEPARATOR
            parts.append(part)
            offset += len(part)

        self._full_text = "".join(parts)
        self._scroll_pos = 0
        self._scroll_timer.start()

    def _get_current_headline_index(self) -> int:
        """Return the index of the headline currently visible at the centre."""
        if not self._headline_offsets:
            return 0

        # Position of the centre of the visible window
        centre = self._scroll_pos + self._display_width // 2
        centre = centre % len(self._full_text)

        # Find which headline contains this position
        for i in range(len(self._headline_offsets) - 1, -1, -1):
            if centre >= self._headline_offsets[i]:
                return i
        return 0

    def _tick(self):
        if not self._full_text:
            return

        # Create a window into the scrolling text (seamless loop)
        doubled = self._full_text + self._full_text
        visible = doubled[self._scroll_pos:self._scroll_pos + self._display_width]
        self._label.setText(visible)

        self._scroll_pos += 1
        if self._scroll_pos >= len(self._full_text):
            self._scroll_pos = 0

    def mousePressEvent(self, event):
        """Open the clicked headline's URL in the browser."""
        if self._headlines and self._full_text:
            # Map click X position to character offset in the scrolling text
            char_width = max(1, self.width() / max(1, self._display_width))
            click_char = int(event.position().x() / char_width)
            abs_pos = (self._scroll_pos + click_char) % len(self._full_text)

            # Find which headline contains that position
            idx = 0
            for i in range(len(self._headline_offsets) - 1, -1, -1):
                if abs_pos >= self._headline_offsets[i]:
                    idx = i
                    break

            url = self._headlines[idx].url
            if url:
                webbrowser.open(url)
        super().mousePressEvent(event)

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
        char_width = 8  # approximate pixel width per character (bold 13px)
        self._display_width = max(40, self.width() // char_width)
