"""Real SEC HTTP/store paths with generated public-source bodies, never a provider."""

from contextlib import contextmanager, ExitStack
from datetime import date, timedelta
import json
import socket
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


def document_body(revision):
    heading = 'ITEM 1. BUSINESS'
    paragraphs = ''.join('<p>Research evidence %d: Caf&#233; &#x8CA1;&#x5831; needle %s.</p>'
                         % (index, revision) for index in range(380))
    return ('<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">'
            '<head><title>Do not show</title></head><body>'
            '<ix:header><ix:hidden>hidden_facts</ix:hidden></ix:header>'
            '<h1>' + heading + '</h1>' + paragraphs +
            '<h1>ITEM 1A. RISK FACTORS</h1><p>Risk evidence for revision ' +
            str(revision) + '.</p></body></html>').encode()

def catalog(cik, *, historical=False, conflicts=False):
    count = 1 if historical else 20 if conflicts else 26
    first = 27 if historical and not conflicts else 1
    rows = {
        'accessionNumber': [f'{cik}-26-{number:06d}' for number in range(first, first + count)],
        'filingDate': [(date(2026, 8, 30) - timedelta(days=number)).isoformat()
                       for number in range(first, first + count)],
        'reportDate': ['2026-06-30'] * count,
        'acceptanceDateTime': ['2026-08-30T15:00:00.000Z'] * count,
        'form': ['10-K/A' if number % 11 == 0 else '10-K' if number % 2 else '10-Q'
                 for number in range(first, first + count)],
        'primaryDocument': [f'fixture-{number}.htm' for number in range(first, first + count)],
    }
    if historical:
        if conflicts:
            rows['primaryDocument'] = ['conflicting-variant.htm']
        return json.dumps(rows).encode()
    return json.dumps({'cik': int(cik), 'filings': {'recent': rows,
        'files': [{'name': f'CIK{cik}-submissions-001.json', 'filingCount': 1,
                   'filingFrom': '2026-01-01', 'filingTo': '2026-12-31'}]}}).encode()


def companyfacts(cik):
    rows = [{'val': 123456789012345678901 + number, 'end': f'{2025-number}-12-31',
             'fy': 2025-number, 'fp': 'FY', 'form': '10-K',
             'accn': f'{cik}-26-{number+1:06d}', 'filed': '2026-02-01',
             'frame': f'CY{2025-number}Q4I'} for number in range(45)]
    return json.dumps({'cik': int(cik), 'facts': {'custom\u8ca1/~ns': {'Assets': {'units': {'USD': rows}}}}}).encode()


@contextmanager
def fixture_app(folder):
    from data_sources.sec_transport import SecResponse, SecTransportFailure
    from src.api.routes import sec_research as api
    from src.profile_state import ProfileStateStore
    from src.sec_research.paths import SecResearchPaths

    folder.mkdir(parents=True, exist_ok=False)
    paths = SecResearchPaths.from_market_db(folder / 'market.db')
    profile = ProfileStateStore(folder / 'profile.db')
    state = {'source_dispatches': [], 'writes': [], 'fail_history': True, 'conflicts': False,
             'document_dispatches': [], 'document_revision': 1, 'document_fail': False,
             'extra_documents': 0}

    class DocumentResponse:
        def __init__(self, body, content_type, status=200):
            self.body, self.content_type, self.status = body, content_type, status
            self.length = len(body)

        def getheader(self, name, default=None):
            return {'Content-Type': self.content_type, 'Content-Length': str(self.length)}.get(name, default)

        def read(self, size):
            part, self.body = self.body[:size], self.body[size:]
            return part

        def close(self):
            self.body = b''

    class DocumentConnection:
        sock = None

        def __init__(self, host, address, *, timeout):
            assert host == 'www.sec.gov'
            self.response = None

        def request(self, method, path, *, headers):
            assert method == 'GET' and path.startswith('/Archives/edgar/data/')
            assert set(headers) == {'Accept', 'Accept-Encoding', 'User-Agent', 'Connection'}
            state['document_dispatches'].append({'path': path, 'identity': headers['User-Agent']})
            body = document_body(state['document_revision'])
            if path.endswith('/index.json'):
                basename = 'fixture-' + str(int(path.split('/')[-2][-6:])) + '.htm'
                extras = [{'name': 'exhibit-' + str(index) + '-' + 'x' * 60 + '.txt',
                           'type': 'text/plain', 'size': ''}
                          for index in range(state['extra_documents'])]
                body = json.dumps({'directory': {'name': path.rsplit('/', 1)[0],
                    'item': [{'name': basename, 'type': 'text/html', 'size': len(body)},
                             {'name': 'exhibit.txt', 'type': 'text/plain', 'size': ''}] + extras}}).encode()
                self.response = DocumentResponse(body, 'application/json')
            elif path.endswith('/exhibit.txt'):
                self.response = DocumentResponse(b'An independent exhibit. needle evidence.', 'text/plain')
            else:
                self.response = DocumentResponse(body, 'text/html; charset=utf-8',
                    status=503 if state['document_fail'] else 200)

        def getresponse(self):
            assert self.response is not None
            return self.response

        def close(self):
            pass

        def abort(self):
            pass

    class FixtureTransport:
        def __init__(self, **kwargs):
            pass

        def get(self, url, **kwargs):
            state['source_dispatches'].append(url)
            leaf = url.rsplit('/', 1)[-1]
            cik = leaf[3:13]
            if len(cik) != 10 or not cik.isascii() or not cik.isdigit():
                raise AssertionError('unexpected fixture source')
            if '-submissions-' in leaf:
                if state['fail_history']:
                    raise SecTransportFailure('sec_rate_limited')
                body = catalog(cik, historical=True, conflicts=state['conflicts'])
            elif '/companyfacts/' in url:
                body = companyfacts(cik)
            else:
                body = catalog(cik, conflicts=state['conflicts'])
            return SecResponse(200, body)

        def close(self):
            pass

    app = FastAPI()
    app.include_router(api.router)
    with ExitStack() as stack:
        stack.enter_context(patch.object(api.SecResearchPaths, 'resolve', lambda: paths))
        stack.enter_context(patch.object(api, 'get_profile_store', lambda: profile))
        stack.enter_context(patch.object(api, 'get_data_provider_store', lambda: SimpleNamespace(
            get_all=lambda: {'sec_edgar': {'user_agent': 'research@arkscope.test'}})))
        stack.enter_context(patch.object(api, 'SecTransport', FixtureTransport))
        from src import lifecycle_public_sources as public
        stack.enter_context(patch.object(public.PublicSourceReader, '_address',
            lambda self, host: (socket.AF_INET, ('93.184.216.34', 443))))
        stack.enter_context(patch.object(public, '_PinnedHTTPSConnection', DocumentConnection))
        stack.enter_context(patch.object(api, 'require_db_write',
            lambda action, detail: state['writes'].append({'action': action, 'detail': detail})))
        with TestClient(app) as client:
            yield client, state, paths
