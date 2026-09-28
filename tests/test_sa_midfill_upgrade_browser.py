"""The operator's disable/reload method must preserve actual installed storage."""

from datetime import datetime
import hashlib
import json
import os
import sqlite3
import subprocess
import time

import pytest

from tests.sa_cutover_assertions import assert_financial_checkpoint_preserved
from tests.sa_midfill_fixture import UpgradeRig, BASELINE, ROOT
from tests.sa_midfill_browser_fixture import InstalledUpgrade
from tests.test_sa_article_acquisition_scope import scope_case


pytestmark = pytest.mark.skipif(os.environ.get('ARKSCOPE_BROWSER_ACCEPTANCE') != '1', reason='isolated installed-browser gate')


@pytest.mark.parametrize('browser', ['firefox', 'chrome'])
@pytest.mark.parametrize('scheduled', [False, True])
def test_installed_midfill_disable_replace_enable(scope_case, tmp_path, monkeypatch, browser, scheduled):
    with UpgradeRig(scope_case, tmp_path, monkeypatch, browser) as rig:
        rig.now = round(time.time(), 3)
        with InstalledUpgrade(rig, browser) as installed:
            installed.call('initialize', scheduled=scheduled)
            installed.call('run')
            # Enabled schedules can win the initial race; wait for that actual
            # run, then submit manual intent at the paced idle boundary.
            snapshot = installed.call('snapshot')
            if scheduled and not snapshot['browser']['companyFinancialRefresh']['pending_scopes']:
                installed.call('run')
            before = {'browser':installed.call('snapshot')['browser'], 'native':rig.native_checkpoint()}
            assert before['browser']['companyCollectorIdentity'] == before['native']['owner']
            ids = before['browser']['companyFinancialRefresh']['pending_scopes']
            assert len(ids) == len(set(ids)) == 3
            saved = [k for k,v in before['browser']['companyFinancialRefresh']['records'].items() if v.get('last_success_at')]
            assert len(saved) == 1
            state = installed.replace('candidate')
            after = {'browser':state['browser'], 'native':rig.native_checkpoint()}
            assert_financial_checkpoint_preserved(before, after)
            wake = after['browser']['companyFinancialRefresh']['next_wake_at']
            assert wake >= datetime.fromisoformat(after['native']['next_navigation_at']).timestamp() * 1000
            job = installed.call('body_start')
            assert job['status'] == 'ok', json.dumps([job, state, rig.messages[-20:]], indent=2)
            assert_financial_checkpoint_preserved(after, {'browser':installed.call('snapshot')['browser'], 'native':rig.native_checkpoint()})
            rig.now += 61; installed.call('clock', now=rig.now*1000)
            body = installed.call('body_wake')
            assert rig.body_is_saved(), body
            rig.now += 61; installed.call('clock', now=rig.now*1000)
            installed.call('run')
            pending = installed.call('snapshot')['browser']['companyFinancialRefresh']['pending_scopes']
            assert pending == ids[1:]
            cancelled = installed.call('body_cancel', job_id=job['job_id'])
            assert cancelled['state'] == 'cancelled', cancelled
            rollback_before = {'browser':installed.call('snapshot')['browser'], 'native':rig.native_checkpoint()}
            old = installed.replace('baseline')
            assert_financial_checkpoint_preserved(rollback_before, {'browser':old['browser'], 'native':rig.native_checkpoint()})
            rig.now += 61; installed.call('clock', now=rig.now*1000)
            installed.call('run')
            news = installed.call('news')
            assert news['status'] == 'ok' and news['acquisition']['priority'] == 'routine', news
            assert rig.body_is_saved() and rig.body_status()['state'] == 'cancelled'
            final = installed.call('snapshot')['browser']
            assert final['companyFinancialRefresh']['pending_scopes'] == ids[2:]
            assert final['saAcquisitionPending'] is None and rig.native_checkpoint()['active'] is None
            with sqlite3.connect(rig.control_path) as conn:
                rows = conn.execute('SELECT task_id,payload,finished_at,receipt FROM acquisition_tasks').fetchall()
            assert all(row[2] and row[3] for row in rows)
            receipts = [json.loads(row[3]) for row in rows]
            assert sum(r.get('body_recovery_job_id') == job['job_id'] for r in receipts) == 1
            financial = [json.loads(row[1]) for row in rows if json.loads(row[1])['operation'] == 'company_financial_capture']
            assert len(financial) == 3
            assert len({json.dumps(row['scope'],sort_keys=True) for row in financial}) == 3
            (tmp_path / 'cutover-receipt.json').write_text(json.dumps({'browser':browser,'baseline':BASELINE,
                'candidate':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'scheduled':scheduled,'pending_before':ids,'pending_after':final['companyFinancialRefresh']['pending_scopes'],
                'checkpoint_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
                'task_ids':[row[0] for row in rows],'body_job_id':job['job_id']}, indent=2))
