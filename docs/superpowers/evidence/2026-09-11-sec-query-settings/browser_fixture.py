"""Real SEC HTTP/store paths with generated public-source bodies, never a provider."""

from contextlib import contextmanager, ExitStack
from datetime import date, timedelta
import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


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
    return json.dumps({'cik': int(cik), 'facts': {'us-gaap': {'Assets': {'units': {'USD': rows}}}}}).encode()


@contextmanager
def fixture_app(folder):
    from data_sources.sec_transport import SecResponse, SecTransportFailure
    from src.api.routes import sec_research as api
    from src.profile_state import ProfileStateStore
    from src.sec_research.paths import SecResearchPaths

    folder.mkdir(parents=True, exist_ok=False)
    paths = SecResearchPaths.from_market_db(folder / 'market.db')
    profile = ProfileStateStore(folder / 'profile.db')
    state = {'source_dispatches': [], 'writes': [], 'fail_history': True, 'conflicts': False}

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
        stack.enter_context(patch.object(api, 'require_db_write',
            lambda action, detail: state['writes'].append({'action': action, 'detail': detail})))
        with TestClient(app) as client:
            yield client, state, paths
