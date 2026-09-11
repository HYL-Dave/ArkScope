"""Reader acceptance against generated sources and actual stored HTTP results."""

from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect


def exercise_documents(page, copy, labels, state, requests, responses, fault,
                       client, output, label):
    state['conflicts'] = False
    state['extra_documents'] = 120
    page.get_by_role('tab', name=copy['catalog'], exact=True).click()
    page.get_by_role('button', name=copy['refresh'], exact=True).click()
    rows = page.locator('.sec-record-scroll tbody tr')
    expect(rows).to_have_count(20)
    first_row = rows.filter(has=page.get_by_text('fixture-1.htm', exact=True))
    reader = page.locator('.sec-document-reader')

    def command(key):
        return reader.get_by_role('button', name=labels[key], exact=True)

    def texts():
        return reader.locator('.sec-document-text').all_text_contents()

    def capture():
        for response in reversed(responses):
            data = response['body'].get('data')
            if '/document' in response['path'] and isinstance(data, dict) and data.get('document'):
                return data['document']['capture_id']
        raise AssertionError('no observed document capture')

    def document_requests():
        return [item for item in requests if '/document' in item['path']]

    def screenshot(suffix):
        reader.locator('h4').scroll_into_view_if_needed()
        page.screenshot(path=str(output / (label + '-reader-' + suffix + '.png')), full_page=True)
        if suffix == 'passages':
            reader.screenshot(path=str(output / (label + '-reader-only.png')))

    def open_first():
        first_row.get_by_role('button', name=labels['open'], exact=True).click()
        expect(reader).to_be_visible()

    def pin(value):
        reader.get_by_label(labels['captureId'], exact=True).fill(value)
        command('pinAction').click()
        expect(reader.locator('.sec-document-text').first).to_be_visible()
        expect(reader).to_contain_text(value)

    before_dispatch = len(state['document_dispatches'])
    open_first()
    expect(reader.locator('.sec-document-text')).to_have_count(0)
    expect(reader.locator('h4')).to_be_in_viewport(ratio=1)
    assert reader.evaluate('(el) => el.contains(document.activeElement)')
    opening_geometry = reader.locator('h4').evaluate('''el => {
      const r = el.getBoundingClientRect();
      return {top:r.top, bottom:r.bottom, viewport:innerHeight,
              visible:r.top>=0 && r.bottom<=innerHeight};
    }''')
    expect(command('acquire')).to_be_enabled()
    assert len(state['document_dispatches']) == before_dispatch
    assert all(item['method'] == 'GET' for item in document_requests())
    screenshot('absent')

    command('acquire').click()
    expect(reader.locator('.sec-document-text').first).to_be_visible()
    assert len(state['document_dispatches']) == before_dispatch + 2
    original = capture()
    original_text = texts()
    assert 'Caf\u00e9 \u8ca1\u5831' in ''.join(original_text)
    assert 'hidden_facts' not in reader.inner_text()
    assert 'needle 1' in ''.join(original_text)
    assert reader.locator('script').count() == 0
    expect(reader).to_contain_text(labels['current'])
    screenshot('passages')

    command('next').click()
    expect(reader.locator('.sec-document-text').first).not_to_have_text(original_text[0])
    next_request = document_requests()[-1]
    params = parse_qs(urlsplit(next_request['path']).query)
    assert params['capture_id'] == [original] and params['max_chars'] == ['6000']
    assert params['document_id'] == ['primary'] and params.get('cursor')
    assert 'query' not in params and 'section_id' not in params
    before_back = len(requests)
    command('previous').click()
    assert texts() == original_text and len(requests) == before_back

    index_pages = 1
    while command('indexNext').is_enabled():
        assert index_pages < 10, 'unbounded index navigation'
        command('indexNext').click()
        page.wait_for_function("!document.querySelector('.sec-document-reader [aria-busy=true]')")
        index_pages += 1
    assert index_pages >= 2
    expect(reader.get_by_label(labels['section'], exact=True).locator('option[value="item_1a"]')).to_have_count(1)
    screenshot('index')
    before_index_back = len(requests)
    command('indexPrevious').click()
    assert len(requests) == before_index_back
    repeat_pages = 0
    while command('indexNext').is_enabled():
        assert repeat_pages < 10, 'unbounded cached index navigation'
        command('indexNext').click()
        page.wait_for_function("!document.querySelector('.sec-document-reader [aria-busy=true]')")
        repeat_pages += 1

    reader.get_by_label(labels['section'], exact=True).select_option('item_1')
    expect(reader.locator('.sec-document-text').first).to_be_visible()
    command('indexPrevious').click()
    expect(reader.get_by_label(labels['section'], exact=True)).to_have_value('item_1')
    reader.get_by_label(labels['search'], exact=True).fill('needle 1')
    command('searchAction').click()
    expect(reader.locator('.sec-document-text').first).to_contain_text('needle 1')
    search_request = document_requests()[-1]
    params = parse_qs(urlsplit(search_request['path']).query)
    assert params['query'] == ['needle 1'] and params['section_id'] == ['item_1']
    assert params['capture_id'] == [original]
    assert reader.get_by_label(labels['document'], exact=True).locator('option').count() > 2
    command('indexNext').click()

    fault['missing_section'] = True
    reader.get_by_label(labels['section'], exact=True).select_option('item_1a')
    expect(reader.locator('.sec-document-text')).to_have_count(0)
    unknown = responses[-1]['body']
    assert any(gap['code'] == 'section_unavailable' for gap in unknown['gaps']), unknown
    before_whole = len(requests)
    command('whole').click()
    expect(reader.locator('.sec-document-text').first).to_be_visible()
    assert len(requests) == before_whole + 1
    params = parse_qs(urlsplit(document_requests()[-1]['path']).query)
    assert 'query' not in params and 'section_id' not in params
    assert texts() == original_text

    command('close').click()
    expect(reader).to_have_count(0)
    expect(first_row.get_by_role('button', name=labels['open'], exact=True)).to_be_focused()
    open_first()
    expect(reader.locator('.sec-document-text').first).to_be_visible()
    expect(reader).to_contain_text(labels['pinned'])
    assert capture() == original and texts() == original_text

    base = '/sec-research/filings/0000320193:0000320193-26-000001/document'
    state['document_revision'] = 2
    other_client = client.post(base, json={'document_id': 'primary'})
    assert other_client.status_code == 200 and other_client.json()['outcome'] == 'complete'
    command('whole').click()
    expect(reader.locator('.sec-document-text').first).to_have_text(original_text[0])
    assert capture() == original
    reader.get_by_label(labels['document'], exact=True).select_option('file:fixture-1.htm')
    expect(reader.locator('.sec-document-text').first).to_have_text(original_text[0])
    reader.get_by_label(labels['document'], exact=True).select_option('primary')
    expect(reader.locator('.sec-document-text').first).to_have_text(original_text[0])
    assert capture() == original
    expect(reader).to_contain_text(labels['pinned'])
    reader.get_by_label(labels['document'], exact=True).select_option('file:exhibit.txt')
    expect(reader.locator('.sec-document-text')).to_have_count(0)
    reader.get_by_label(labels['document'], exact=True).select_option('primary')
    expect(reader.locator('.sec-document-text').first).to_have_text(original_text[0])
    assert capture() == original
    command('currentAction').click()
    expect(reader.locator('.sec-document-text').first).to_contain_text('needle 2')
    newer = capture()
    assert newer != original
    expect(reader).to_contain_text(labels['current'])
    pin(original)
    assert texts() == original_text

    state['document_fail'] = True
    command('acquire').click()
    expect(reader.locator('.sec-document-text')).to_have_count(0)
    failed = next(item['body'] for item in reversed(responses)
                  if item['method'] == 'POST' and '/document' in item['path'])
    assert failed['outcome'] == 'failed'
    screenshot('failed-latest')
    pin(original)
    assert texts() == original_text

    reader.get_by_label(labels['document'], exact=True).select_option('file:fixture-1.htm')
    expect(reader.locator('.sec-document-text').first).to_have_text(original_text[0])
    reader.get_by_label(labels['document'], exact=True).select_option('primary')
    expect(reader.locator('.sec-document-text').first).to_have_text(original_text[0])
    assert capture() == original

    # The known failed response is held while the same filing reader is remounted.
    fault['hold_next_acquisition'] = True
    command('acquire').click()
    page.wait_for_timeout(50)
    assert fault.get('held_acquisition')
    command('close').click()
    expect(reader).to_have_count(0)
    open_first()
    expect(reader.get_by_text(labels['unknownOutcome'], exact=True)).to_be_visible()
    expect(command('acquire')).to_be_disabled()
    held, known_response = fault.pop('held_acquisition')
    known_attempt = known_response.json()
    assert known_attempt['outcome'] == 'failed'
    held.fulfill(status=known_response.status_code, content_type='application/json', body=known_response.content)
    expect(reader.get_by_text(labels['unknownOutcome'], exact=True)).to_have_count(0)
    expect(command('acquire')).to_be_enabled()
    expect(reader.locator('.sec-document-text').first).to_have_text(original_text[0])

    state['document_fail'] = False
    state['document_revision'] = 3
    fault['lose_next_document'] = True
    command('acquire').click()
    expect(reader.get_by_text(labels['unknownOutcome'], exact=True)).to_be_visible()
    expect(command('acquire')).to_be_disabled()
    post_count = sum(item['method'] == 'POST' for item in document_requests())
    command('reread').click()
    expect(reader.locator('.sec-document-text').first).to_contain_text('needle 3')
    assert sum(item['method'] == 'POST' for item in document_requests()) == post_count
    screenshot('unknown-reread')

    # An unacquired file must not display the primary's retained passages.
    reader.get_by_label(labels['document'], exact=True).select_option('file:exhibit.txt')
    expect(reader.locator('.sec-document-text')).to_have_count(0)
    expect(reader).to_contain_text(labels['directoryCapture'])
    assert reader.get_by_label(labels['document'], exact=True).locator('option[value="primary"]').count() == 1
    reader.get_by_label(labels['document'], exact=True).select_option('primary')
    expect(reader.locator('.sec-document-text').first).to_contain_text('needle 3')

    # Hold one actual API result, then release it after closing and selecting a new filing.
    fault['hold_next_document'] = True
    reader.get_by_label(labels['search'], exact=True).fill('needle 3')
    command('searchAction').click()
    page.wait_for_timeout(50)
    assert fault.get('held_document')
    command('close').click()
    other_row = rows.filter(has=page.get_by_text('fixture-3.htm', exact=True))
    other_row.get_by_role('button', name=labels['open'], exact=True).click()
    expect(reader).to_contain_text('fixture-3.htm')
    intercept, response = fault.pop('held_document')
    intercept.fulfill(status=response.status_code, content_type='application/json', body=response.content)
    page.wait_for_timeout(50)
    expect(reader.locator('.sec-document-text')).to_have_count(0)
    expect(reader).not_to_contain_text('needle 3')
    screenshot('late-result')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    command('close').click()

    page.get_by_role('tab', name=copy['facts'], exact=True).click()
    expect(rows).to_have_count(40)
    return {'original_capture': original, 'newer_capture': newer,
            'opening_geometry': opening_geometry,
            'index_pages': index_pages, 'next_request': next_request,
            'search_request': search_request, 'other_client_attempt': other_client.json(),
            'failed_attempt': failed, 'lost_post_count_after_reread': post_count,
            'known_completion_after_reopen': known_attempt,
            'primary_alias_preserved_pin': True, 'index_back_kept_section': True,
            'stale_response_ignored': True, 'section_fault': fault.get('section_fault_record')}
