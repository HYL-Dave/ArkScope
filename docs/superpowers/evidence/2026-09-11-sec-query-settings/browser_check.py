"""Exercise the real SEC panel and routes using only disposable local data."""

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

HTML = '''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SEC fixture preview</title></head><body><div id="root"></div>
<script type="module">import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{};
window.$RefreshSig$=()=>type=>type; window.__vite_plugin_react_preamble_installed__=true;</script>
<script type="module" src="/@vite/client"></script><script type="module">
import React from '/node_modules/.vite/deps/react.js';
import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
import i18n from '/node_modules/.vite/deps/i18next.js';
import {initializeI18n, resources} from '/src/i18n/resources.ts';
import {installUiTokens} from '/src/ui/tokens.ts';
import {SecResearchPanel} from '/src/settings/SecResearchPanel.tsx';
import '/src/styles.css'; import '/src/ui/primitives.css';
const locale = new URL(location.href).searchParams.get('locale') || 'zh-Hant';
await initializeI18n(i18n, locale); document.documentElement.lang=locale;
window.__secCopy = resources[locale].settings.secResearch;
installUiTokens(document.documentElement);
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement('main',
 {style:{maxWidth:'1120px',padding:'16px',margin:'0 auto'}},
 React.createElement(SecResearchPanel)));
</script></body></html>'''
HTML = HTML.replace('/node_modules/.vite', '/@fs' + str(WORK / 'vite-cache'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    for name, leaf in {'HOME': 'home', 'XDG_CONFIG_HOME': 'home/config',
                       'XDG_CACHE_HOME': 'home/cache', 'ARKSCOPE_LOCK_DIR': 'locks'}.items():
        path = args.output / leaf
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    for name, leaf in {'ARKSCOPE_PROFILE_DB': 'profile.db', 'ARKSCOPE_MARKET_DB': 'market.db',
                       'ARKSCOPE_SA_DB': 'sa.db', 'ARKSCOPE_MACRO_CALENDAR_DB': 'macro.db',
                       'ARKSCOPE_TOKEN_STORE_PATH': 'tokens.json'}.items():
        os.environ[name] = str(args.output / leaf)
    import offline_pytest  # Installs production-file/provider-network audit hooks.
    from src import env_keys
    env_keys._loaded = True
    from browser_fixture import fixture_app
    from playwright.sync_api import expect, sync_playwright

    netloc = urlsplit(args.base).netloc
    reports = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for locale in ('zh-Hant', 'en'):
                for width, height in ((1280, 960), (390, 844)):
                    label = f'{locale}-{width}'
                    with fixture_app(args.output / (label + '-store')) as (client, state, _):
                        context = browser.new_context(viewport={'width': width, 'height': height},
                                                      timezone_id='Asia/Taipei')
                        context.add_init_script('window.arkscope={apiBase:' + json.dumps(args.base + '/__mock') + '};')
                        page = context.new_page()
                        errors, requests, responses, fault = [], [], [], {'lose_next_refresh': False}
                        duplicate_key_warnings = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda message: duplicate_key_warnings.append(message.text)
                                if 'same key' in message.text or 'unique "key"' in message.text else None)

                        def route(intercept):
                            request = intercept.request
                            url = urlsplit(request.url)
                            if url.netloc != netloc:
                                errors.append('unexpected_network')
                                return intercept.abort()
                            if url.path == '/__sec-preview':
                                return intercept.fulfill(status=200, content_type='text/html', body=HTML)
                            if not url.path.startswith('/__mock/'):
                                return intercept.continue_()
                            path = url.path.removeprefix('/__mock') + ('?' + url.query if url.query else '')
                            requests.append({'method': request.method, 'path': path})
                            body = request.post_data_json if request.post_data else None
                            response = client.request(request.method, path, json=body)
                            responses.append({'method': request.method, 'path': path,
                                              'status': response.status_code, 'body': response.json()})
                            (args.output / (label + '-responses.json')).write_text(json.dumps(responses, indent=2))
                            if fault['lose_next_refresh'] and request.method == 'POST':
                                fault['lose_next_refresh'] = False
                                return intercept.abort('failed')
                            return intercept.fulfill(status=response.status_code,
                                content_type='application/json', body=response.content)

                        page.route('**/*', route)
                        page.goto(args.base + '/__sec-preview?locale=' + locale)
                        page.wait_for_function('!!window.__secCopy')
                        copy = page.evaluate('window.__secCopy')
                        budget = page.get_by_label(copy['budget'], exact=True)
                        expect(budget).to_have_value('100')
                        assert not state['source_dispatches'], 'mount acquired a provider source'
                        assert requests == [{'method': 'GET', 'path': '/sec-research/config'}], requests
                        page.screenshot(path=str(args.output / (label + '-initial.png')), full_page=True)
                        page.get_by_label('CIK', exact=True).fill('320193')
                        page.get_by_role('button', name=copy['load'], exact=True).click()
                        expect(page.locator('[role=status][data-state=unavailable]').first).to_be_visible()
                        assert not state['source_dispatches'], 'stored read acquired a provider source'
                        invalid = page.evaluate('''async () => {
                          const response=await fetch(window.arkscope.apiBase+'/sec-research/0000320193/facts?period=unknown');
                          return {status:response.status, body:await response.json()};
                        }''')
                        assert invalid == {'status': 422, 'body': {'detail': {'code': 'sec_research_query_invalid'}}}, invalid

                        rows = page.locator('.sec-record-scroll tbody tr')
                        page.get_by_role('button', name=copy['refresh'], exact=True).click()
                        expect(rows).to_have_count(20)
                        expect(page.locator('[role=status][data-state=partial]').first).to_be_visible()
                        assert len(state['source_dispatches']) == 3, state
                        first_catalog = rows.all_text_contents()
                        page.get_by_role('button', name=copy['next'], exact=True).click()
                        expect(rows).to_have_count(6)
                        before_back = len(requests)
                        page.get_by_role('button', name=copy['previous'], exact=True).click()
                        expect(rows).to_have_count(20)
                        assert rows.all_text_contents() == first_catalog
                        assert len(requests) == before_back, 'previous page unexpectedly reread'

                        state['fail_history'] = False
                        before_resume = len(state['source_dispatches'])
                        page.get_by_role('button', name=copy['resume'], exact=True).click()
                        expect(rows).to_have_count(20)
                        expect(page.locator('[role=status][data-state=ok]').first).to_be_visible()
                        assert len(state['source_dispatches']) == before_resume + 1, state
                        page.get_by_role('button', name=copy['next'], exact=True).click()
                        expect(rows).to_have_count(7)
                        page.get_by_label(copy['forms'], exact=True).fill('10-K')
                        page.get_by_label(copy['amendments'], exact=True).uncheck()
                        page.get_by_role('button', name=copy['load'], exact=True).click()
                        expect(rows).to_have_count(13)
                        expect(page.get_by_role('button', name=copy['next'], exact=True)).to_be_disabled()
                        page.screenshot(path=str(args.output / (label + '-catalog.png')), full_page=True)
                        page.get_by_label(copy['forms'], exact=True).fill('8-K')
                        page.get_by_role('button', name=copy['load'], exact=True).click()
                        expect(rows).to_have_count(0)
                        expect(page.locator('[role=status][data-state=empty]')).to_be_visible()

                        state['conflicts'] = True
                        page.get_by_label(copy['forms'], exact=True).fill('')
                        page.get_by_label(copy['amendments'], exact=True).check()
                        page.get_by_role('button', name=copy['refresh'], exact=True).click()
                        expect(rows).to_have_count(20)
                        expect(page.locator('[role=status][data-state=partial]').first).to_be_visible()
                        expect(page.get_by_role('cell', name='fixture-1.htm', exact=True)).to_be_visible()
                        expect(page.get_by_role('cell', name='conflicting-variant.htm', exact=True)).to_be_visible()
                        conflict_first = rows.all_text_contents()
                        page.get_by_role('button', name=copy['next'], exact=True).click()
                        expect(rows).to_have_count(1)
                        expect(page.get_by_role('cell', name='fixture-20.htm', exact=True)).to_be_visible()
                        conflict_next = rows.all_text_contents()
                        before_conflict_back = len(requests)
                        page.get_by_role('button', name=copy['previous'], exact=True).click()
                        expect(rows).to_have_count(20)
                        assert rows.all_text_contents() == conflict_first
                        assert len(requests) == before_conflict_back, 'conflict back reread'
                        page.get_by_role('button', name=copy['next'], exact=True).click()
                        expect(rows).to_have_count(1)
                        assert rows.all_text_contents() == conflict_next
                        assert not duplicate_key_warnings, duplicate_key_warnings
                        page.screenshot(path=str(args.output / (label + '-conflict-next.png')), full_page=True)

                        page.get_by_role('tab', name=copy['facts'], exact=True).click()
                        expect(rows).to_have_count(40)
                        page.screenshot(path=str(args.output / (label + '-facts-first.png')), full_page=True)
                        expect(page.get_by_role('cell', name='123456789012345678945', exact=True)).to_be_visible()
                        first_facts = rows.all_text_contents()
                        page.get_by_role('button', name=copy['next'], exact=True).click()
                        expect(rows).to_have_count(5)
                        expect(page.get_by_role('cell', name='123456789012345678901', exact=True)).to_be_visible()
                        page.get_by_role('button', name=copy['previous'], exact=True).click()
                        expect(rows).to_have_count(40)
                        assert rows.all_text_contents() == first_facts

                        fault['lose_next_refresh'] = True
                        page.get_by_role('button', name=copy['refresh'], exact=True).click()
                        expect(page.get_by_text(copy['unconfirmed'], exact=True)).to_be_visible()
                        post_count = sum(item['method'] == 'POST' for item in requests)
                        page.get_by_role('button', name=copy['reread'], exact=True).click()
                        expect(rows).to_have_count(40)
                        assert sum(item['method'] == 'POST' for item in requests) == post_count

                        before_save = len(state['source_dispatches'])
                        page.get_by_label(copy['unit'], exact=True).select_option('bytes')
                        budget.fill('1')
                        page.get_by_role('button', name=copy['save'], exact=True).click()
                        expect(page.get_by_text(copy['saved'], exact=True)).to_be_visible()
                        expect(page.get_by_text(copy['overBudget'], exact=True)).to_be_visible()
                        expect(budget).to_have_value('1')
                        page.get_by_role('button', name=copy['load'], exact=True).click()
                        expect(rows).to_have_count(40)
                        assert len(state['source_dispatches']) == before_save
                        assert rows.all_text_contents() == first_facts
                        page.screenshot(path=str(args.output / (label + '-facts.png')), full_page=True)
                        geometry = page.locator('.sec-pagination .ui-icon-button').evaluate_all('''buttons => buttons.map(button => {
                          const b=button.getBoundingClientRect(), s=button.querySelector('svg').getBoundingClientRect();
                          return {button:[b.x,b.y,b.right,b.bottom], icon:[s.x,s.y,s.right,s.bottom],
                            contained:s.x>=b.x && s.y>=b.y && s.right<=b.right && s.bottom<=b.bottom};
                        })''')
                        assert len(geometry) == 2 and all(item['contained'] for item in geometry), geometry
                        headers = page.locator('.sec-record-scroll thead th').all_text_contents()
                        assert headers[0:2] == [copy['concept'], copy['value']], headers
                        table_geometry = page.locator('.sec-record-scroll').evaluate('''el => ({
                          height:el.clientHeight, width:el.clientWidth,
                          scrollHeight:el.scrollHeight, scrollWidth:el.scrollWidth})''')
                        assert table_geometry['height'] <= 600, table_geometry
                        budget.fill('0')
                        expect(page.get_by_role('button', name=copy['save'], exact=True)).to_be_disabled()
                        expect(page.get_by_text(copy['invalidBudget'], exact=True)).to_be_visible()
                        assert not errors, errors
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        assert page.locator('.sec-record-scroll').evaluate('(el) => el.scrollWidth >= el.clientWidth')
                        reports.append({'locale': locale, 'viewport': [width, height],
                                        'requests': requests, 'state': state, 'errors': errors,
                                        'pagination_geometry': geometry, 'fact_headers': headers,
                                        'table_geometry': table_geometry,
                                        'conflict_pagination': {'first_rows': conflict_first, 'next_rows': conflict_next,
                                                                'duplicate_key_warnings': duplicate_key_warnings},
                                        'absent_store_invalid_filter': invalid})
                        context.close()
        finally:
            browser.close()
    (args.output / 'results.json').write_text(json.dumps(reports, indent=2) + '\n')
    print(json.dumps([{'locale': item['locale'], 'viewport': item['viewport'],
                      'http_requests': len(item['requests']),
                      'fixture_source_dispatches': len(item['state']['source_dispatches']),
                      'errors': item['errors']} for item in reports]), flush=True)


if __name__ == '__main__':
    main()
