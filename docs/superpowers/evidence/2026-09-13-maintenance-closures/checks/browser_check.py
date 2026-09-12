"""Disposable EIR-001 primitive fixture checks; never boots the application."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
GEOMETRY = """() => {
  const bounds = (node) => {
    const r = node.getBoundingClientRect();
    const s = getComputedStyle(node);
    return {x:r.x, y:r.y, width:r.width, height:r.height, right:r.right, bottom:r.bottom,
      display:s.display, direction:s.flexDirection, wrap:s.flexWrap, gap:s.gap,
      fontSize:s.fontSize, color:s.color, marginBottom:s.marginBottom,
      scrollWidth:node.scrollWidth, clientWidth:node.clientWidth};
  };
  const selectors = ['main', '.ui-page-header', '.ui-page-header-copy',
    '.ui-page-header h1', '.ui-page-header-actions', '.detailpage-head', '[role=status]'];
  const elements = Object.fromEntries(selectors.map((s) => [s, bounds(document.querySelector(s))]));
  const overlap = (a,b) => Math.min(a.right,b.right)-Math.max(a.x,b.x)>0.5
    && Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>0.5;
  const textOverflow = [];
  const walker = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.textContent.trim()) continue;
    const range = document.createRange(); range.selectNodeContents(node);
    const parent = node.parentElement.getBoundingClientRect();
    for (const r of range.getClientRects()) {
      if (r.left < parent.left-1 || r.right > parent.right+1 || r.top < parent.top-1 || r.bottom > parent.bottom+1)
        textOverflow.push(node.textContent);
    }
  }
  const buttons = [...document.querySelectorAll('button')].map(bounds);
  return {elements, buttons, textOverflow,
    horizontalOverflow: document.documentElement.scrollWidth > innerWidth
      || Object.values(elements).some((r) => r.scrollWidth > r.clientWidth+1 || r.x < 0 || r.right > innerWidth+1),
    titleActionsOverlap: overlap(elements['.ui-page-header-copy'], elements['.ui-page-header-actions']),
    buttonOverlap: buttons.some((a,i) => buttons.slice(i+1).some((b) => overlap(a,b))),
    headerDetailOverlap: overlap(elements['.ui-page-header'], elements['.detailpage-head']),
    styleSources: [...document.querySelectorAll('style[data-vite-dev-id]')].map((s) => s.dataset.viteDevId),
    retiredDom: document.querySelectorAll('.page-head, .page-head-actions').length,
    icons: document.querySelectorAll('.ui-page-header-actions svg').length};
}"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=('before', 'after'), required=True)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ['TMPDIR'] = str(args.output)
    tempfile.tempdir = str(args.output)
    origin = urlparse(args.base).netloc
    paths = ['styles.css', 'shell/shell.css', 'ui/primitives.css', 'settings/settings.css',
             'ui/PageHeader.tsx', 'ui/Button.tsx', 'ui/tokens.ts', 'ui/tokens.json']
    record = {'phase': args.phase, 'base': args.base, 'cases': [], 'denied': [],
              'requests': [], 'consoleErrors': [], 'pageErrors': [], 'failedRequests': [],
              'browserClosed': False, 'fixtureOnly': True,
              'sourceSha256': {p: hashlib.sha256((ROOT / 'apps/arkscope-web/src' / p).read_bytes()).hexdigest()
                               for p in paths}}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--disable-background-networking'])
            record['browserVersion'] = browser.version
            try:
                context = browser.new_context(device_scale_factor=1, service_workers='block', reduced_motion='reduce')

                def route(request_route):
                    request = request_route.request
                    url = urlparse(request.url)
                    if url.netloc != origin or any(part in url.path for part in ('/api', '/App.tsx', '/main.tsx')):
                        record['denied'].append(request.url)
                        request_route.abort()
                    else:
                        record['requests'].append(request.url)
                        request_route.continue_()

                context.route('**/*', route)
                for surface in ('general', 'settings'):
                    for width in (320, 390, 760, 761, 1440):
                        name = f'{surface}-{width}'
                        page = context.new_page()
                        page.set_viewport_size({'width': width, 'height': 900})
                        page.on('pageerror', lambda error: record['pageErrors'].append(str(error)))
                        page.on('console', lambda message: record['consoleErrors'].append(message.text)
                                if message.type == 'error' else None)
                        page.on('requestfailed', lambda request: record['failedRequests'].append(request.url))
                        try:
                            page.goto(f'{args.base}/?surface={surface}', wait_until='networkidle')
                            page.locator('.ui-page-header h1').wait_for()
                            page.evaluate('document.fonts.ready')
                            geometry = page.evaluate(GEOMETRY)
                            assert geometry['retiredDom'] == 0, name
                            assert geometry['icons'] == 2, name
                            assert not geometry['horizontalOverflow'], (name, geometry)
                            assert not geometry['textOverflow'], (name, geometry['textOverflow'])
                            assert not geometry['titleActionsOverlap'], name
                            assert not geometry['buttonOverlap'], name
                            assert not geometry['headerDetailOverlap'], name
                            assert geometry['elements']['.ui-page-header']['display'] == 'flex', name
                            assert geometry['elements']['.ui-page-header']['wrap'] == 'wrap', name
                            assert geometry['elements']['.ui-page-header h1']['fontSize'] == '22px', name
                            assert geometry['elements']['.detailpage-head']['display'] == 'flex', name
                            assert geometry['elements']['.detailpage-head']['gap'] == '12px', name
                            assert [p.rsplit('/src/', 1)[-1] for p in geometry['styleSources']] == paths[:4], geometry
                            screenshot = args.output / f'{name}.png'
                            page.screenshot(path=str(screenshot), animations='disabled', full_page=True)
                            pixels = Image.open(screenshot).convert('RGB')
                            colors = pixels.getcolors(pixels.width * pixels.height)
                            assert len(colors) > 100, (name, 'blank or missing styles')
                            assert pixels.getpixel((0, 0)) == (14, 17, 22), (name, 'actual theme missing')
                            page.get_by_role('button', name='Refresh', exact=True).click()
                            assert page.get_by_role('status').inner_text() == 'Refreshed', name
                            assert page.get_by_role('button', name='Export activity', exact=True).is_disabled(), name
                            case = {'name': name, 'width': width, 'height': 900, 'geometry': geometry,
                                    'screenshot': str(screenshot), 'screenshotSha256': hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                                    'uniqueColors': len(colors), 'interaction': 'passed'}
                            if args.compare:
                                prior = json.loads((args.compare / 'results.json').read_text())
                                before = next(c for c in prior['cases'] if c['name'] == name)
                                assert before['geometry'] == geometry, (name, 'geometry changed')
                                with Image.open(args.compare / f'{name}.png') as baseline:
                                    diff = ImageChops.difference(baseline.convert('RGB'), pixels)
                                    case['differentPixels'] = sum(p != (0, 0, 0) for p in diff.getdata())
                                    assert case['differentPixels'] == 0, name
                                case['geometryEquivalent'] = True
                            record['cases'].append(case)
                        finally:
                            page.close()
                assert not record['denied'], record['denied']
                assert not record['consoleErrors'], record['consoleErrors']
                assert not record['pageErrors'], record['pageErrors']
                assert not record['failedRequests'], record['failedRequests']
                context.close()
            finally:
                browser.close()
                record['browserClosed'] = True
    finally:
        (args.output / 'results.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'phase': args.phase, 'cases': len(record['cases']), 'browserClosed': record['browserClosed'],
                      'differentPixels': [c.get('differentPixels') for c in record['cases']],
                      'denied': record['denied'], 'pageErrors': record['pageErrors']}))


if __name__ == '__main__':
    main()
