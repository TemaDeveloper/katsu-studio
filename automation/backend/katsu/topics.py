"""Free publisher headlines for topic inspiration; never a generation request."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import httpx

from .store import atomic_json


@dataclass(frozen=True)
class Feed:
    url: str
    publisher: str
    origins: tuple[str, ...]


# Listed by the publishers at /newsfeeds.htm, /rss/, and /rss-feeds/.
# Fixed endpoints only: feed entries and browser inputs never become fetch targets.
FEEDS = (
    Feed('https://www.sciencedaily.com/rss/mind_brain.xml', 'ScienceDaily', ('www.sciencedaily.com', 'sciencedaily.com')),
    Feed('https://www.smithsonianmag.com/rss/history/', 'Smithsonian Magazine', ('www.smithsonianmag.com', 'smithsonianmag.com')),
    Feed('https://www.smithsonianmag.com/rss/science-nature/', 'Smithsonian Magazine', ('www.smithsonianmag.com', 'smithsonianmag.com')),
    Feed('https://www.nasa.gov/feed/', 'NASA', ('www.nasa.gov', 'nasa.gov', 'science.nasa.gov')),
)
MAX_FEED_BYTES = 512_000
MAX_FEED_ITEMS = 60
MAX_EXCLUDED_IDS = MAX_FEED_ITEMS * len(FEEDS)
CACHE_TTL = timedelta(minutes=30)
FAILURE_RETRY = timedelta(minutes=5)


class _PlainTitle(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _title(raw: str) -> str:
    parser = _PlainTitle()
    parser.feed(unescape(raw))
    value = ' '.join(''.join(parser.parts).split())
    value = re.sub(r'[\x00-\x1f\x7f]', '', value)
    return value if len(value) <= 300 else value[:297].rstrip() + '…'


def _date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            value = parsedate_to_datetime(raw)
        except (ValueError, TypeError, OverflowError):
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _url(raw: str, feed: Feed) -> str | None:
    if not raw.strip():
        return None
    try:
        parsed = urlsplit(urljoin(feed.url, unescape(raw).strip()))
        if (parsed.scheme != 'https' or parsed.hostname not in feed.origins or
                parsed.username or parsed.password or parsed.port not in (None, 443)):
            return None
        # Strip only tracking parameters; preserve query values that identify articles.
        query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                 if not key.lower().startswith('utm_') and key.lower() not in ('fbclid', 'gclid')]
        return urlunsplit(('https', parsed.hostname, parsed.path or '/', urlencode(query), ''))
    except ValueError:
        return None


def _item(title: str, url: str, published: str | None, feed: Feed) -> dict | None:
    topic, source_url = _title(title), _url(url, feed)
    if len(topic) < 3 or not source_url:
        return None
    published_at = _date(published)
    return {'id': hashlib.sha256(source_url.encode()).hexdigest()[:20], 'topic': topic,
            'source_name': feed.publisher, 'source_url': source_url,
            'published_at': published_at.isoformat() if published_at else None}


def _parse(content: bytes, feed: Feed) -> list[dict]:
    # The verified feeds are UTF-8. Decode before rejecting declarations so UTF-16
    # cannot disguise an entity declaration; never enable DTD or entity expansion.
    document = content.decode('utf-8-sig')
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', document, re.IGNORECASE):
        raise ValueError('Feed declarations are not supported.')
    root = ET.fromstring(document)
    name = root.tag.rsplit('}', 1)[-1]
    if name not in ('rss', 'RDF', 'feed'):
        raise ValueError('Not an RSS or Atom feed.')
    items = []
    for entry in root.iter():
        if entry.tag.rsplit('}', 1)[-1] not in ('item', 'entry'):
            continue
        fields = {child.tag.rsplit('}', 1)[-1]: child for child in entry}
        title = fields.get('title')
        links = [child for child in entry if child.tag.rsplit('}', 1)[-1] == 'link'
                 and child.attrib.get('rel', 'alternate') == 'alternate']
        if title is None or not links:
            continue
        link = links[0]
        date = next((fields[key] for key in ('pubDate', 'published', 'updated', 'date') if key in fields), None)
        item = _item(''.join(title.itertext()), link.attrib.get('href') or ''.join(link.itertext()),
                     ''.join(date.itertext()) if date is not None else None, feed)
        if item:
            items.append(item)
        if len(items) >= MAX_FEED_ITEMS:
            break
    return items


async def _fetch(client: httpx.AsyncClient, feed: Feed) -> list[dict]:
    async with asyncio.timeout(8):
        target = feed.url
        for _ in range(3):
            if not _url(target, feed):
                raise ValueError('Unapproved feed origin.')
            async with client.stream('GET', target) as response:
                if response.is_redirect:
                    location = response.headers.get('location')
                    if not location:
                        raise ValueError('Missing feed redirect.')
                    target = urljoin(target, location)
                    continue
                response.raise_for_status()
                length = response.headers.get('content-length')
                if length and int(length) > MAX_FEED_BYTES:
                    raise ValueError('Feed is too large.')
                chunks, size = [], 0
                async for chunk in response.aiter_bytes(chunk_size=64_000):
                    size += len(chunk)
                    if size > MAX_FEED_BYTES:
                        raise ValueError('Feed is too large.')
                    chunks.append(chunk)
                return _parse(b''.join(chunks), feed)
        raise ValueError('Too many feed redirects.')


class TopicService:
    def __init__(self, root: Path, *, transport: httpx.AsyncBaseTransport | None = None,
                 clock: Callable[[], datetime] | None = None):
        self.cache_path = Path(root) / 'topics' / 'cache.json'
        self.transport = transport
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock = asyncio.Lock()
        self.snapshot = self._read_cache()

    def _read_cache(self) -> dict:
        try:
            if self.cache_path.stat().st_size > MAX_FEED_BYTES:
                return {}
            raw = json.loads(self.cache_path.read_text())
            if not isinstance(raw, dict) or not _date(raw.get('checked_at')):
                return {}
            saved = {}
            for feed in FEEDS:
                record = raw.get('feeds', {}).get(feed.url, {})
                if not isinstance(record, dict) or not _date(record.get('updated_at')):
                    continue
                items = []
                for value in record.get('items', [])[:MAX_FEED_ITEMS]:
                    if not isinstance(value, dict):
                        continue
                    if not isinstance(value.get('topic'), str) or not isinstance(value.get('source_url'), str):
                        continue
                    item = _item(value['topic'], value['source_url'], value.get('published_at'), feed)
                    if item:
                        items.append(item)
                saved[feed.url] = {'items': items, 'updated_at': record['updated_at']}
            failed = [url for url in raw.get('failed_feeds', []) if url in {feed.url for feed in FEEDS}]
            return {'checked_at': raw['checked_at'], 'feeds': saved, 'failed_feeds': failed}
        except (OSError, ValueError, TypeError, AttributeError, OverflowError):
            return {}

    async def _refresh(self, now: datetime):
        async with httpx.AsyncClient(transport=self.transport, follow_redirects=False,
                                     timeout=httpx.Timeout(5, connect=3),
                                     limits=httpx.Limits(max_connections=4),
                                     headers={'User-Agent': 'KatsuStudio/0.1 (local RSS reader)',
                                              'Accept': 'application/rss+xml, application/atom+xml, application/xml'}) as client:
            fetched = await asyncio.gather(*(_fetch(client, feed) for feed in FEEDS), return_exceptions=True)
        records = dict(self.snapshot.get('feeds', {}))
        failed = []
        for feed, result in zip(FEEDS, fetched):
            if isinstance(result, BaseException):
                failed.append(feed.url)
            else:
                records[feed.url] = {'items': result, 'updated_at': now.isoformat()}
        self.snapshot = {'checked_at': now.isoformat(), 'feeds': records, 'failed_feeds': failed}
        try:
            atomic_json(self.cache_path, self.snapshot)
        except OSError:
            pass  # The in-memory cache still keeps this form usable.

    async def page(self, offset=0, limit=5, *, exclude_ids: tuple[str, ...] | None = None) -> dict:
        if not 0 <= offset <= 1000 or not 1 <= limit <= 5:
            raise ValueError('Invalid topic pagination.')
        if exclude_ids is not None and (len(exclude_ids) > MAX_EXCLUDED_IDS or
                any(not re.fullmatch(r'[0-9a-f]{20}', value) for value in exclude_ids)):
            raise ValueError('Invalid excluded topic IDs.')
        async with self.lock:
            now = self.clock()
            checked_at = _date(self.snapshot.get('checked_at'))
            ttl = FAILURE_RETRY if self.snapshot.get('failed_feeds') else CACHE_TTL
            cached = bool(checked_at and timedelta(0) <= now - checked_at < ttl)
            if not cached:
                await self._refresh(now)
            records = self.snapshot.get('feeds', {})
            failed = self.snapshot.get('failed_feeds', [])
            publishers: dict[str, list[dict]] = {}
            updated = []
            for feed in FEEDS:
                record = records.get(feed.url)
                if record:
                    publishers.setdefault(feed.publisher, []).extend(record['items'])
                    updated.append(record['updated_at'])
            queues = {name: deque(sorted(items, key=lambda item: item['published_at'] or '', reverse=True))
                      for name, items in publishers.items()}
            items, seen_urls, seen_titles = [], set(), set()
            while any(queues.values()):
                for queue in queues.values():
                    while queue:
                        item = queue.popleft()
                        title_key = re.sub(r'[^\w]+', ' ', item['topic'].casefold()).strip()
                        if item['source_url'] in seen_urls or title_key in seen_titles:
                            continue
                        seen_urls.add(item['source_url'])
                        seen_titles.add(title_key)
                        items.append(item)
                        break
            stale = any(url in records and records[url]['items'] for url in failed)
            unavailable = list(dict.fromkeys(feed.publisher for feed in FEEDS if feed.url in failed))
            if not items:
                notice = 'Publisher feeds are unavailable right now. You can still enter your own topic.'
            elif len(failed) == len(FEEDS):
                notice = 'Publisher feeds are unavailable right now. Showing saved headlines.'
            elif failed:
                notice = 'Some feeds are unavailable (' + ', '.join(unavailable) + '). '
                notice += 'Showing available and saved headlines.' if stale else 'Showing available headlines.'
            else:
                notice = 'Showing cached feed headlines.' if cached else None
            if exclude_ids is not None:
                excluded = set(exclude_ids)
                items = [item for item in items if item['id'] not in excluded]
                offset = 0
            return {'items': items[offset:offset + limit], 'has_more': offset + limit < len(items),
                    'notice': notice, 'updated_at': max(updated) if updated else None, 'stale': bool(stale)}
