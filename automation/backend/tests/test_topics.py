"""Topic suggestions exercise real parsing, persistence, and the public route.

Only the public HTTP boundary is replaced; no project or provider is invoked.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from html import escape
from importlib import import_module

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katsu.store import Store


SCIENCE = 'https://www.sciencedaily.com/rss/mind_brain.xml'
HISTORY = 'https://www.smithsonianmag.com/rss/history/'
SMITH_SCIENCE = 'https://www.smithsonianmag.com/rss/science-nature/'
NASA = 'https://www.nasa.gov/feed/'
TODAY = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def modules():
    try:
        return import_module('katsu.topics'), import_module('katsu.topic_routes')
    except ModuleNotFoundError:
        pytest.fail('The sourced topic suggestions feature is not implemented yet.')


def rss(items):
    return ('<?xml version="1.0"?><rss version="2.0"><channel><title>Publisher</title>' + ''.join(
        '<item><title>' + escape(title) + '</title><link>' + escape(url) + '</link>'
        '<pubDate>Fri, 02 Oct 2026 14:00:00 GMT</pubDate><description>Do not copy this article body.</description></item>'
        for title, url in items) + '</channel></rss>').encode()


def successful_feeds():
    return {
        SCIENCE: rss([(f'Brain discovery {i}', f'https://www.sciencedaily.com/releases/2026/10/brain-{i}.htm') for i in range(4)]),
        HISTORY: rss([(f'History discovery {i}', f'https://www.smithsonianmag.com/history/discovery-{i}/') for i in range(3)]),
        SMITH_SCIENCE: rss([('History discovery 0', 'https://www.smithsonianmag.com/history/discovery-0/?utm_source=rss'),
                            ('Science discovery', 'https://www.smithsonianmag.com/science-nature/discovery/')]),
        NASA: rss([(f'Space discovery {i}', f'https://www.nasa.gov/missions/discovery-{i}/') for i in range(4)]),
    }


def transport_for(feeds):
    def handle(request):
        value = feeds[str(request.url)]  # Unrecognized URLs must fail, not silently receive a fixture.
        if isinstance(value, Exception):
            raise value
        if isinstance(value, httpx.Response):
            return value
        return httpx.Response(200, content=value, headers={'Content-Type': 'application/rss+xml'})
    return httpx.MockTransport(handle)


def service(tmp_path, feeds, clock=lambda: TODAY):
    topics, _ = modules()
    return topics.TopicService(tmp_path, transport=transport_for(feeds), clock=clock)


def page(svc, offset=0, limit=5):
    return asyncio.run(svc.page(offset, limit))


def test_api_returns_five_diverse_sourced_ideas_then_five_more_without_a_project(tmp_path):
    # Catches a feed-concatenation implementation, duplicate articles, or pagination overlap.
    topics, routes = modules()
    store = Store(tmp_path)
    app = FastAPI()
    routes.attach_topic_routes(app, store)
    app.state.topics = topics.TopicService(store.root, transport=transport_for(successful_feeds()), clock=lambda: TODAY)
    with TestClient(app) as client:
        first_response = client.get('/api/topics?offset=0&limit=5')
        assert first_response.status_code == 200
        first = first_response.json()
        second = client.get('/api/topics?offset=5&limit=5').json()
    assert [item['source_name'] for item in first['items'][:3]] == ['ScienceDaily', 'Smithsonian Magazine', 'NASA']
    assert len(first['items']) == len(second['items']) == 5
    assert not {item['id'] for item in first['items']} & {item['id'] for item in second['items']}
    assert first['has_more'] and second['has_more']
    assert first['stale'] is False
    assert first['updated_at'] == '2026-10-03T12:00:00+00:00'
    assert first['items'][0] == {
        'id': first['items'][0]['id'], 'topic': 'Brain discovery 0', 'source_name': 'ScienceDaily',
        'source_url': 'https://www.sciencedaily.com/releases/2026/10/brain-0.htm',
        'published_at': '2026-10-02T14:00:00+00:00',
    }
    assert store.list_projects() == []
    assert len(page(app.state.topics, 10)['items']) == 2
    assert page(app.state.topics, 10)['has_more'] is False


def test_view_more_excludes_displayed_ideas_after_headlines_refresh(tmp_path):
    # Catches repeated original pages after newer headlines change numeric offsets.
    topics, routes = modules()
    feeds, now = successful_feeds(), [TODAY]
    app = FastAPI()
    routes.attach_topic_routes(app, Store(tmp_path))
    app.state.topics = topics.TopicService(tmp_path, transport=transport_for(feeds), clock=lambda: now[0])
    with TestClient(app) as client:
        displayed = client.get('/api/topics?offset=0&limit=5').json()['items']
        newer = {
            SCIENCE: [('New brain idea one', 'https://www.sciencedaily.com/new-brain-one.htm'),
                      ('New brain idea two', 'https://www.sciencedaily.com/new-brain-two.htm')],
            HISTORY: [('New history idea', 'https://www.smithsonianmag.com/history/new-idea/')],
            NASA: [('New space idea one', 'https://www.nasa.gov/new-space-one/'),
                   ('New space idea two', 'https://www.nasa.gov/new-space-two/')],
        }
        for url, items in newer.items():
            added = rss(items).replace(b'Fri, 02 Oct 2026 14:00:00 GMT', b'Sat, 03 Oct 2026 14:00:00 GMT')
            feeds[url] = feeds[url].replace(b'</channel>', added.split(b'<title>Publisher</title>')[1].split(b'</channel>')[0] + b'</channel>')
        now[0] += timedelta(hours=1)
        # Deliberately supply the old numeric offset too: exclude mode must select
        # from all unseen ideas rather than skip five more after excluding them.
        for expected_count in (5, 5, 2):
            excluded = ','.join(item['id'] for item in displayed)
            response = client.get('/api/topics', params={'offset': 5, 'limit': 5, 'exclude': excluded})
            assert response.status_code == 200
            result = response.json()
            assert len(result['items']) == expected_count
            assert not {item['id'] for item in displayed} & {item['id'] for item in result['items']}
            displayed.extend(result['items'])
        assert result['has_more'] is False
    assert len(displayed) == 17


@pytest.mark.parametrize('exclude', ['', 'not-an-id', 'A' * 20, 'f' * 19,
                                     ','.join(['f' * 20] * 241), 'f' * 6001],
                         ids=['blank', 'invalid', 'uppercase', 'short', 'too-many', 'too-long'])
def test_route_rejects_invalid_or_excessive_exclusion_ids(tmp_path, exclude):
    # Catches accepting arbitrary values or an unbounded exclusion query.
    topics, routes = modules()
    app = FastAPI()
    routes.attach_topic_routes(app, Store(tmp_path))
    app.state.topics = topics.TopicService(tmp_path, transport=transport_for(successful_feeds()), clock=lambda: TODAY)
    with TestClient(app) as client:
        assert client.get('/api/topics', params={'exclude': exclude}).status_code == 422


def test_recent_cache_survives_restart_and_does_not_need_the_network(tmp_path):
    # Catches in-memory-only caching or unnecessary publisher requests on every page.
    initial = page(service(tmp_path, successful_feeds()))
    offline = {url: AssertionError('A fresh cache must not request a publisher.') for url in successful_feeds()}
    cached = page(service(tmp_path, offline, clock=lambda: TODAY + timedelta(minutes=1)))
    assert cached['items'] == initial['items']
    assert cached['stale'] is False
    assert 'cached' in cached['notice'].lower()
    assert cached['updated_at'] == initial['updated_at']


def test_expired_feed_refresh_replaces_headlines_and_keeps_failed_feed_cache_honestly(tmp_path):
    # Catches data loss on partial failure and stale data falsely presented as refreshed.
    page(service(tmp_path, successful_feeds()))
    changed = successful_feeds()
    changed[SCIENCE] = httpx.ConnectError('Publisher offline')
    changed[NASA] = rss([('New space discovery', 'https://www.nasa.gov/new-discovery/')])
    refreshed = page(service(tmp_path, changed, clock=lambda: TODAY + timedelta(hours=1)), limit=5)
    assert refreshed['stale'] is True
    assert 'ScienceDaily' in refreshed['notice']
    assert 'saved' in refreshed['notice'].lower()
    assert any(item['topic'] == 'Brain discovery 0' for item in refreshed['items'])
    assert any(item['topic'] == 'New space discovery' for item in refreshed['items'])
    assert not any(item['topic'].startswith('Space discovery') for item in refreshed['items'])


def test_partial_first_load_shows_real_available_headlines(tmp_path):
    # Catches invented filler or complete failure when only one publisher is unavailable.
    feeds = successful_feeds()
    feeds[HISTORY] = httpx.Response(503)
    feeds[SMITH_SCIENCE] = httpx.Response(403)
    result = page(service(tmp_path, feeds))
    assert len(result['items']) == 5
    assert {item['source_name'] for item in result['items']} == {'ScienceDaily', 'NASA'}
    assert 'Smithsonian Magazine' in result['notice']
    assert result['stale'] is False


def test_all_feeds_unavailable_returns_an_honest_empty_result(tmp_path):
    # Catches hard-coded fallback ideas and unhandled provider errors.
    feeds = {url: httpx.ConnectError('Offline') for url in successful_feeds()}
    result = page(service(tmp_path, feeds))
    assert result['items'] == []
    assert result['has_more'] is False
    assert result['updated_at'] is None
    assert result['stale'] is False
    assert 'unavailable' in result['notice'].lower()


def test_all_feeds_unavailable_can_use_existing_cache_and_back_off(tmp_path):
    # Catches cache deletion on outage and repeat refreshes from successive View more clicks.
    page(service(tmp_path, successful_feeds()))
    now = [TODAY + timedelta(hours=1)]
    offline = {url: httpx.ReadTimeout('Offline') for url in successful_feeds()}
    result = page(service(tmp_path, offline, clock=lambda: now[0]))
    assert len(result['items']) == 5 and result['stale']
    assert 'saved' in result['notice'].lower() and 'unavailable' in result['notice'].lower()
    cached_only = {url: AssertionError('Failure cache should back off before retrying.') for url in successful_feeds()}
    now[0] += timedelta(minutes=1)
    assert page(service(tmp_path, cached_only, clock=lambda: now[0]), offset=5)['stale']


def test_feed_titles_are_plain_text_and_article_links_stay_on_publisher_origins(tmp_path):
    # Catches HTML injection, excessive topics, invalid dates, and unsafe source destinations.
    feeds = {url: httpx.Response(503) for url in successful_feeds()}
    feeds[SCIENCE] = rss([
        ('<b>Why do brains learn?</b> & more', 'https://www.sciencedaily.com/releases/brain.htm?utm_source=rss#read'),
        ('Private endpoint', 'http://127.0.0.1/secrets'),
        ('Fake publisher', 'https://www.sciencedaily.com.evil.example/article'),
        ('Unsafe scheme', 'javascript:alert(1)'),
        ('Long ' + 'title ' * 90, 'https://www.sciencedaily.com/releases/long.htm'),
    ]).replace(b'Fri, 02 Oct 2026 14:00:00 GMT', b'invalid date')
    result = page(service(tmp_path, feeds))
    assert len(result['items']) == 2
    assert result['items'][0]['topic'] == 'Why do brains learn? & more'
    assert result['items'][0]['source_url'] == 'https://www.sciencedaily.com/releases/brain.htm'
    assert result['items'][0]['published_at'] is None
    assert len(result['items'][1]['topic']) <= 300


def test_missing_article_link_cannot_become_a_suggestion_link_to_the_feed_itself(tmp_path):
    # Catches resolving an empty link against the feed URL instead of an article.
    feeds = {url: httpx.Response(503) for url in successful_feeds()}
    feeds[SCIENCE] = rss([('A headline without an article', '')])
    result = page(service(tmp_path, feeds))
    assert result['items'] == []


@pytest.mark.parametrize('bad_xml', [
    b'<!DOCTYPE rss [<!ENTITY unsafe "expanded">]><rss><channel><item><title>&unsafe;</title></item></channel></rss>',
    '<!DOCTYPE rss [<!ENTITY unsafe "expanded">]><rss/>'.encode('utf-16'),
    b'<rss><channel><item>broken',
])
def test_unsafe_or_malformed_xml_is_reported_as_unavailable(tmp_path, bad_xml):
    # Catches entity expansion and parser errors reaching the form as a server error.
    result = page(service(tmp_path, {url: bad_xml for url in successful_feeds()}))
    assert result['items'] == []
    assert 'unavailable' in result['notice'].lower()


def test_redirects_cannot_request_an_unapproved_origin(tmp_path):
    # Catches SSRF through a feed redirect; the external boundary rejects unexpected URLs.
    feeds = {url: httpx.Response(302, headers={'Location': 'http://127.0.0.1/secrets'}) for url in successful_feeds()}
    result = page(service(tmp_path, feeds))
    assert result['items'] == []
    assert 'unavailable' in result['notice'].lower()


def test_oversized_feed_is_rejected_without_discarding_other_publishers(tmp_path):
    # Catches unbounded feed downloads or one bad response taking down the entire suggestion list.
    feeds = successful_feeds()
    feeds[SCIENCE] = b'<rss>' + b'x' * 600_000 + b'</rss>'
    result = page(service(tmp_path, feeds))
    assert len(result['items']) == 5
    assert not any(item['source_name'] == 'ScienceDaily' for item in result['items'])
    assert 'ScienceDaily' in result['notice']


def test_atom_entries_and_duplicate_titles_are_parsed_without_article_bodies(tmp_path):
    # Catches RSS-only parsing and title duplicates with different URLs.
    feeds = {url: httpx.Response(503) for url in successful_feeds()}
    feeds[NASA] = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Learning about Mars</title>
    <link rel="alternate" href="https://science.nasa.gov/mars/discovery/"/><published>2026-10-02T10:00:00Z</published>
    <content>Article body must never be returned.</content></entry><entry><title>Learning about Mars</title>
    <link href="https://www.nasa.gov/mars/duplicate/"/></entry></feed>'''
    result = page(service(tmp_path, feeds))
    assert len(result['items']) == 1
    assert result['items'][0]['published_at'] == '2026-10-02T10:00:00+00:00'
    assert 'Article body' not in str(result)


def test_route_validates_pagination_and_does_not_accept_arbitrary_feed_urls(tmp_path):
    # Catches unbounded public pagination and user-controlled network targets.
    topics, routes = modules()
    app = FastAPI()
    routes.attach_topic_routes(app, Store(tmp_path))
    app.state.topics = topics.TopicService(tmp_path, transport=transport_for(successful_feeds()), clock=lambda: TODAY)
    with TestClient(app) as client:
        for query in ('offset=-1', 'limit=0', 'limit=6', 'offset=1001'):
            assert client.get('/api/topics?' + query).status_code == 422
        assert client.get('/api/topics?url=http://127.0.0.1/secrets').status_code == 200


def test_corrupt_disk_cache_does_not_break_empty_offline_results(tmp_path):
    # Catches an unreadable cache preventing the create form from loading its suggestions.
    cache = tmp_path / 'topics' / 'cache.json'
    cache.parent.mkdir()
    cache.write_text('{not JSON')
    result = page(service(tmp_path, {url: httpx.ConnectError('Offline') for url in successful_feeds()}))
    assert result['items'] == [] and 'unavailable' in result['notice'].lower()
