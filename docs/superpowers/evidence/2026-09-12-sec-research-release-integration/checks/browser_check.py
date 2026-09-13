"""Task7 real Settings/scheduler boundary, disposable loopback only."""
import argparse
from contextlib import ExitStack
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse
from urllib.request import urlopen

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
RUN = Path(os.environ['ARKSCOPE_OFFLINE_TEST_WORKSPACE'])
sys.path.insert(0, str(ROOT))
import offline_pytest  # unchanged offline audit guard, including loopback-only sockets

for name, leaf in {'HOME': 'home', 'XDG_CONFIG_HOME': 'home/config',
        'XDG_CACHE_HOME': 'home/cache', 'TMPDIR': 'tmp', 'ARKSCOPE_LOCK_DIR': 'locks'}.items():
    path = RUN / leaf
    path.mkdir(parents=True, exist_ok=True)
    os.environ[name] = str(path)
for name, leaf in {'ARKSCOPE_PROFILE_DB': 'profile.db', 'ARKSCOPE_MARKET_DB': 'market.db',
        'ARKSCOPE_SA_DB': 'sa.db', 'ARKSCOPE_MACRO_CALENDAR_DB': 'macro.db',
        'ARKSCOPE_TOKEN_STORE_PATH': 'unused-tokens.json'}.items():
    os.environ[name] = str(RUN / leaf)
from src import env_keys
env_keys._loaded = True
from browser_fixture import fixture_app
from playwright.sync_api import sync_playwright, expect


def save(path, value):
    with path.open('x') as output:
        json.dump(value, output, indent=2, ensure_ascii=True)
        output.write('\n')


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_until(fn, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if fn():
            return
        time.sleep(.05)
    raise AssertionError('fixture wait exceeded')


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    records, measurements, page_errors, console_errors, external = [], [], [], [], []
    with fixture_app(output / 'stores') as (client, state, paths):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                path = urlparse(self.path).path
                fixtures = {
                    '/config/model-catalog': {'models': [], 'routes': {}, 'tasks': [], 'credentials': {}},
                    '/providers/health': {'providers': [], 'jobs': {}, 'notes': [], 'local_market': {'db_exists': False, 'sync': {}}},
                    '/providers/config': {'providers': {}, 'setup': {'required': False}},
                    '/sa/extension-health': {'chain_state': 'interrupted',
                        'generated_at': '2026-09-13T00:00:00Z', 'segments': []},
                    '/security-lifecycle/cases': {'cases': [], 'count': 0,
                        'queue_counts': {'attention': 0, 'monitoring': 0, 'history': 0},
                        'admission_counts': {'admitted': 0, 'needs_review': 0, 'pending': 0, 'screened_out': 0},
                        'data_integrity': {'source_missing_count': 0}},
                    '/market-data/trading-days': {'version': 2, 'market_scope': 'us_listed_equity_proxy',
                        'coverage_session': 'rth', 'interval': '15min', 'lookback_days': 15,
                        'universe_count': 0, 'generated_at_et': '2026-09-12T20:00:00-04:00',
                        'calendar_health': {'status': 'ok', 'reason_codes': [],
                            'reviewed_through': '2026-09-13', 'forward_horizon_months': 12},
                        'observation_health': {'status': 'ok', 'reason_code': None},
                        'days': [], 'provider_errors': []},
                    '/market-data/price-repair/operations': {'version': 1, 'operations': [],
                        'total': 0, 'offset': 0, 'has_more': False},
                    '/security-lifecycle/automation': {'config_status': 'valid',
                        'config': {'enabled': False, 'interval_minutes': 30, 'batch_limit': 2,
                            'apply_profile_transitions': False},
                        'schedule': {'status': 'disabled', 'last_attempt_at': None, 'next_scheduled_at': None},
                        'telemetry_status': 'absent', 'last_status': None, 'last_result': None,
                        'active_incident': None, 'latest_failed_runs': [], 'current_progress': []},
                    '/news/status': {'market_db': str(paths.market_db_path), 'exists': False,
                        'news': {'row_count': 0, 'source_count': 0, 'latest_published': None},
                        'normalized_writes_setting': False, 'normalized_writes_setting_explicit': False,
                        'normalized_writes_env_override': False, 'normalized_writes_env_value': None,
                        'write_route': 'legacy_local', 'write_route_reason': 'setting', 'sync': None},
                    '/macro/status': {'macro_db': str(RUN / 'macro.db'), 'exists': False,
                        'tables': {}, 'use_local_macro_setting': False, 'env_override': False,
                        'local_first_active': False},
                    '/macro/snapshot': {'available': False, 'macro_db': str(RUN / 'macro.db'),
                        'series_count': 0, 'observation_count': 0, 'release_dates_count': 0,
                        'latest_fetched_at': None, 'items': [], 'missing_series': []},
                    '/market-data/status': {'exists': False, 'market_db': str(paths.market_db_path),
                        'prices': {'row_count': 0, 'ticker_count': 0, 'latest_datetime': None},
                        'news': {'row_count': 0, 'source_count': 0, 'latest_published': None},
                        'fundamentals': {'row_count': 0, 'ticker_count': 0, 'latest_date': None},
                        'financial_cache': {'row_count': 0, 'valid_count': 0, 'expired_count': 0, 'latest_fetched_at': None},
                        'sync': {'prices': None, 'news': None, 'fundamentals': None}},
                }
                if path in fixtures and self.command_name == 'GET':
                    status, payload = 200, json.dumps(fixtures[path]).encode()
                    owner = 'unrelated-empty-fixture'
                else:
                    response = client.request(self.command_name, self.path, content=body,
                        headers={'Content-Type': 'application/json'})
                    status, payload = response.status_code, response.content
                    owner = 'real-route'
                records.append({'method': self.command_name, 'path': self.path,
                    'body': json.loads(body) if body else None, 'status': status,
                    'phase': state['phase'], 'owner': owner, 'response_sha256': hashlib.sha256(payload).hexdigest()})
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                self.command_name = 'GET'
                self.respond()

            def do_POST(self):
                self.command_name = 'POST'
                self.respond()

            def do_PUT(self):
                self.command_name = 'PUT'
                self.respond()

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, name='task7-fixture-http')
        thread.start()
        vite_port = port()
        base = f'http://127.0.0.1:{vite_port}'
        env = dict(os.environ, FIXTURE_VITE_PORT=str(vite_port),
            FIXTURE_API=f'http://127.0.0.1:{server.server_port}')
        cmd = ['/home/hyl/.nvm/versions/node/v22.14.0/bin/node',
            str(ROOT / 'node_modules/vite/bin/vite.js'), '--config', str(WORK / 'vite-preview.mjs')]
        save(output / 'server-command.json', {'command': cmd, 'cwd': str(ROOT),
            'base': base, 'fixture_api': env['FIXTURE_API'], 'home': env['HOME']})
        with (output / 'vite.log').open('x') as log:
            process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                def ready():
                    if process.poll() is not None:
                        raise AssertionError('Vite failed: ' + (output / 'vite.log').read_text())
                    try:
                        return urlopen(base, timeout=.5).status == 200
                    except OSError:
                        return False
                wait_until(ready)
                seeded = client.post('/sec-research/320193/refresh', json={}).json()
                assert seeded['status'] == 'partial', seeded
                catalog = client.get('/sec-research/320193/filings').json()
                filing_id = catalog['data'][0]['filing_id']
                acquired = client.post(f'/sec-research/filings/{filing_id}/document', json={'document_id': 'primary'})
                assert acquired.status_code == 200 and acquired.json()['status'] in {'ok', 'partial'}, acquired.text
                save(output / 'seed.json', {'refresh': seeded, 'filings': catalog, 'document': acquired.json()})
                initial_dispatches = len(state['source_dispatches'])
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    try:
                        for locale in ('en', 'zh-Hant'):
                            for width, height in ((1280, 960), (390, 844)):
                                case = f'{locale}-{width}x{height}'
                                state['phase'] = case + '-stored'
                                page = browser.new_page(viewport={'width': width, 'height': height})
                                page.on('pageerror', lambda error: page_errors.append(str(error)))
                                page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
                                def guard(route):
                                    if urlparse(route.request.url).hostname in {'127.0.0.1', 'localhost'}:
                                        route.continue_()
                                    else:
                                        external.append(route.request.url)
                                        route.abort()
                                page.route('**/*', guard)
                                page.goto(base + '/?lang=' + locale)
                                is_en = locale == 'en'
                                budget = page.get_by_label('Capture budget' if is_en else '擷取容量上限', exact=True)
                                expect(budget).to_be_visible()
                                row = page.locator('[data-source-id="sec_research_filings"]')
                                expect(row).to_have_count(1)
                                toggle = row.locator('input[type="checkbox"]')
                                expect(toggle).not_to_be_checked()
                                await_dispatches = len(state['source_dispatches'])
                                await_documents = len(state['document_dispatches'])
                                toggle.click()
                                expect(toggle).to_be_checked()
                                toggle.click()
                                expect(toggle).not_to_be_checked()
                                interval = row.locator('input[type="number"]')
                                interval.fill('720')
                                interval.press('Enter')
                                interval.blur()
                                wait_until(lambda: client.get('/schedule').json()['sources']['sec_research_filings']['interval_minutes'] == 720)
                                interval.fill('1440')
                                interval.press('Enter')
                                interval.blur()
                                wait_until(lambda: client.get('/schedule').json()['sources']['sec_research_filings']['interval_minutes'] == 1440)
                                assert len(state['source_dispatches']) == await_dispatches
                                assert len(state['document_dispatches']) == await_documents
                                page.get_by_label('CIK', exact=True).fill('320193')
                                page.get_by_role('button', name='Load local' if is_en else '讀取本機', exact=True).click()
                                expect(page.locator('.sec-record-scroll tbody tr')).to_have_count(20)
                                page.get_by_role('button', name='Read filing' if is_en else '閱讀申報文件', exact=True).first.click()
                                expect(page.locator('.sec-document-text').first).to_contain_text('Research evidence')
                                page.get_by_role('button', name='Open pinned capture' if is_en else '開啟固定擷取版本', exact=True).click()
                                page.get_by_role('button', name='Next page' if is_en else '下一頁', exact=True).first.click()
                                expect(page.locator('.sec-record-scroll tbody tr')).to_have_count(6)
                                budget.fill('150')
                                pinned_text = json.dumps(page.locator('.sec-document-text').all_text_contents())
                                pinned_catalog = page.locator('.sec-record-scroll').inner_text()
                                pinned_id = page.get_by_label('Capture ID' if is_en else '擷取 ID', exact=True).input_value()
                                local_reads = lambda: [r for r in records if r['phase'] == state['phase'] and '/sec-research/320193' in r['path']]
                                state['phase'] = case + '-schedule'
                                before_requests = len(state['source_dispatches'])
                                before_documents = len(state['document_dispatches'])
                                state['blocked'].clear()
                                state['release'].clear()
                                state['block'] = True
                                state['fail_facts'] = True
                                row.locator('td').nth(3).get_by_role('button').click()
                                wait_until(state['blocked'].is_set)
                                page.evaluate("window.dispatchEvent(new Event('focus'))")
                                page.wait_for_timeout(200)
                                state['release'].set()
                                state['block'] = False
                                wait_until(lambda: not client.get('/schedule').json()['sources']['sec_research_filings']['running'])
                                page.evaluate("window.dispatchEvent(new Event('focus'))")
                                expect(page.locator('.sec-schedule-status')).to_have_attribute('data-batch-status', 'partial')
                                expect(budget).to_have_value('150')
                                assert json.dumps(page.locator('.sec-document-text').all_text_contents()) == pinned_text
                                assert page.locator('.sec-record-scroll').inner_text() == pinned_catalog
                                assert page.get_by_label('Capture ID' if is_en else '擷取 ID', exact=True).input_value() == pinned_id
                                assert not local_reads(), local_reads()
                                batch = client.get('/sec-research/schedule-status').json()
                                assert batch['data']['last_attempt']['request_count'] == 5
                                assert batch['data']['last_attempt']['confirmed_ciks'] == ['0000320193']
                                assert batch['data']['last_attempt']['failed_ciks'] == ['0000789019']
                                assert batch['data']['last_acquisition_at'] is not None
                                requests = state['source_dispatches'][before_requests:]
                                assert len(requests) == 5 and all('-submissions-' not in url for url in requests)
                                assert len(state['document_dispatches']) == before_documents
                                notices = page.locator('.errorbox:visible').all_text_contents()
                                assert all('started' in text and ('SEC Research' if is_en else 'SEC 財務研究') in text for text in notices), notices
                                expect(page.get_by_text('Loading...' if is_en else '載入中...', exact=True)).to_have_count(0)
                                page.locator('.sec-schedule-status').scroll_into_view_if_needed()
                                page.screenshot(path=str(output / (case + '-status.png')))
                                geometry = page.evaluate("""() => {
                                  const root=document.documentElement;
                                  const status=document.querySelector('.sec-schedule-status');
                                  const rects=[...status.querySelectorAll('dt,dd')].map(e=>({text:e.textContent,
                                    x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,
                                    width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}));
                                  const overlap=[];
                                  for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){
                                    const a=rects[i],b=rects[j];
                                    if(a.x<b.x+b.width-.5 && b.x<a.x+a.width-.5 && a.y<b.y+b.height-.5 && b.y<a.y+a.height-.5)overlap.push([i,j]);
                                  }
                                  return {viewport:[innerWidth,innerHeight],documentWidth:root.scrollWidth,
                                    rects,overlap,clipped:[...status.querySelectorAll('button,input,dt,dd')]
                                      .filter(e=>e.scrollWidth>e.clientWidth+1).map(e=>({tag:e.tagName,text:e.textContent}))};
                                }""")
                                assert geometry['documentWidth'] <= width and not geometry['overlap'] and not geometry['clipped'], geometry
                                row.scroll_into_view_if_needed()
                                page.screenshot(path=str(output / (case + '-controls.png')))
                                controls_geometry = row.evaluate("""el => {
                                  const scroll=el.closest('.settings-table-scroll');
                                  const clipped=[...el.querySelectorAll('input,button')].filter(e=>e.scrollWidth>e.clientWidth+1)
                                    .map(e=>({tag:e.tagName,text:e.textContent}));
                                  scroll.scrollLeft=0;
                                  return {clientWidth:scroll.clientWidth,scrollWidth:scroll.scrollWidth,clipped};
                                }""")
                                assert not controls_geometry['clipped'], controls_geometry
                                page.screenshot(path=str(output / (case + '-controls-source.png')))
                                page.locator('.sec-document-reader').scroll_into_view_if_needed()
                                page.screenshot(path=str(output / (case + '-pinned.png')))
                                measurements.append({'case': case, 'geometry': geometry, 'controls_geometry': controls_geometry,
                                    'existing_run_now_notices': notices,
                                    'pinned_capture_id': pinned_id,
                                    'pinned_text_sha256': hashlib.sha256(pinned_text.encode()).hexdigest(),
                                    'catalog_sha256': hashlib.sha256(pinned_catalog.encode()).hexdigest(),
                                    'dirty_budget': '150', 'body_requests': requests, 'batch': batch})
                                page.close()
                    finally:
                        if 'page' in locals() and not page.is_closed():
                            page.screenshot(path=str(output / 'last-page.png'))
                            with (output / 'last-page.html').open('x') as content:
                                content.write(page.content())
                        browser.close()
                assert not page_errors, page_errors
                assert not external, external
                assert not console_errors, console_errors
                assert all(row['status'] == 200 for row in records), records
                assert initial_dispatches == 3
            finally:
                state['release'].set()
                process.terminate()
                process.wait(timeout=15)
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                save(output / 'api-requests.json', records)
                save(output / 'source-inventory.json', {key: value for key, value in state.items()
                    if key not in {'blocked', 'release'}})
                save(output / 'browser-results.json', {'measurements': measurements, 'page_errors': page_errors,
                    'console_errors': console_errors, 'external_requests': external,
                    'unrelated_generated_endpoints': sorted({urlparse(row['path']).path for row in records
                        if row['owner'] == 'unrelated-empty-fixture'}),
                    'verification_scope': 'Actual Settings SEC panel and shared scheduler only; unrelated sections use generated empty/disabled fixture responses, not product health evidence.',
                    'servers_stopped': process.poll() is not None and not thread.is_alive()})
    print(json.dumps({'browser_cases': len(measurements), 'output': str(output), 'servers_stopped': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.output)
