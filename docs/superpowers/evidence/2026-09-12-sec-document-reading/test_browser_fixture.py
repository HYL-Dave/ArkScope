"""Preflight the browser fixture through the real HTTP/service/store boundary."""

import json

from browser_fixture import fixture_app
from browser_check import verify_document_passages


def test_generated_browser_transport_retains_real_document_semantics(tmp_path):
    with fixture_app(tmp_path / 'fixture') as (client, state, paths):
        base = '/sec-research/filings/0000320193:0000320193-26-000001/document'
        assert client.get(base).json()['status'] == 'unavailable'
        assert not state['document_dispatches']
        response = client.post('/sec-research/0000320193/refresh', json={})
        assert response.status_code == 200, response.text
        response = client.post(base, json={'document_id': 'primary'})
        assert response.status_code == 200, response.text
        attempt = response.json()
        assert attempt['outcome'] == 'complete', attempt
        assert len(state['document_dispatches']) == 2
        index = client.get(base).json()
        assert index['status'] == 'partial', index
        assert any(row['document_id'] == 'file:exhibit.txt' for row in index['data']['documents'])
        capture = index['data']['document']['capture_id']
        page = client.get(base, params={'capture_id': capture,
                                      'cursor': index['data']['text_start_cursor']}).json()
        checks = verify_document_passages(page, paths)
        assert checks
        text = ''.join(item['text'] for item in page['data']['passages'])
        assert 'Caf\u00e9 \u8ca1\u5831' in text and 'hidden_facts' not in text
        state['document_revision'] = 2
        assert client.post(base, json={'document_id': 'primary'}).json()['outcome'] == 'complete'
        assert client.get(base).json()['data']['document']['capture_id'] != capture
        assert client.get(base, params={'capture_id': capture,
                                       'cursor': index['data']['text_start_cursor']}).json() == page
        state['document_fail'] = True
        failed = client.post(base, json={'document_id': 'primary'}).json()
        assert failed['outcome'] == 'failed', failed
        assert client.get(base).json()['status'] == 'unavailable'
        pinned = client.get(base, params={'capture_id': capture}).json()
        assert pinned['data']['document']['capture_id'] == capture
        (tmp_path / 'interface-examples.json').write_text(json.dumps({
            'attempt': attempt, 'index': index, 'page': page, 'failed': failed,
            'pinned': pinned, 'citations_checked': checks, 'dispatches': state['document_dispatches'],
        }, indent=2))
