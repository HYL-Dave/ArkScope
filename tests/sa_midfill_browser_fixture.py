"""Same-ID installed package replacement, without uninstall or storage repair."""

from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from tests.sa_midfill_fixture import BASELINE, ROOT, baseline_source
from tests.test_sa_extension_packaging import _load_builder


def package(rig, browser, version):
    source = rig.root / (version + '-source')
    source.mkdir(exist_ok=True)
    prefix = 'extensions/sa_alpha_picks/'
    files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE if version == 'baseline' else 'HEAD', prefix], cwd=ROOT, text=True)
    for name in files.splitlines():
        relative = Path(name.removeprefix(prefix))
        if len(relative.parts) != 1 or relative.suffix not in {'.js', '.json', '.css', '.html'}:
            continue
        (source / relative).write_text(baseline_source(name) if version == 'baseline' else (ROOT / name).read_text())
    built = rig.root / (version + '-built')
    if browser == 'firefox': _load_builder().build_firefox(source, built)
    else: shutil.copytree(source, built, dirs_exist_ok=True)
    manifest = json.loads((built / 'manifest.json').read_text())
    manifest['host_permissions'] = ['http://127.0.0.1/*']
    manifest['permissions'] = [p for p in manifest['permissions'] if p != 'nativeMessaging']
    manifest['name'] = 'ArkScope Isolated Midfill Gate'
    if browser == 'firefox':
        manifest['browser_specific_settings']['gecko']['id'] = 'midfill-gate@arkscope.local'
        scripts = manifest['background']['scripts']
        manifest['background']['scripts'] = [scripts[0], 'fixture_pre.js', *scripts[1:], 'fixture_hooks.js']
    else:
        manifest['background']['service_worker'] = 'fixture_worker.js'
        (built / 'fixture_worker.js').write_text("importScripts('fixture_pre.js','background.js','fixture_hooks.js');")
    (built / 'manifest.json').write_text(json.dumps(manifest))
    pre = (f'var ARK_FIXTURE_URL={json.dumps(rig.url)},ARK_FIXTURE_CLIENT={json.dumps(rig.client)},'
           f'ARK_FIXTURE_VERSION={json.dumps(version)},ARK_FIXTURE_CLOCK={rig.now * 1000};\n')
    pre += """
    Date.now=()=>ARK_FIXTURE_CLOCK;
    const fixtureCreate=chrome.tabs.create.bind(chrome.tabs);
    chrome.tabs.create=opts=>fixtureCreate({...opts,url:ARK_FIXTURE_URL+'/page'});
    chrome.runtime.sendNativeMessage=(_host,_msg,cb)=>{const result={status:'error',error_code:'fixture_disabled'};if(cb)cb(result);return Promise.resolve(result);};
    chrome.runtime.connectNative=()=>{
      const listeners=new Set();
      return {onMessage:{addListener:fn=>listeners.add(fn),removeListener:fn=>listeners.delete(fn)},
        onDisconnect:{addListener(){},removeListener(){}},
        postMessage(){Promise.resolve().then(()=>listeners.forEach(fn=>fn({status:'ok'})));},disconnect(){}};
    };
    """
    (built / 'fixture_pre.js').write_text(pre)
    shutil.copyfile(ROOT / 'tests/js/sa_midfill_browser_hooks.js', built / 'fixture_hooks.js')
    (built / 'fixture.html').write_text('<!doctype html><title>Isolated upgrade driver</title>')
    installed = getattr(rig, 'install_folder', rig.root / 'installed')
    shutil.copytree(built, installed, dirs_exist_ok=True)
    return installed


class InstalledUpgrade(ExitStack):
    def __init__(self, rig, browser):
        super().__init__()
        self.rig, self.browser = rig, browser

    def __enter__(self):
        super().__enter__()
        try:
            if self.browser == 'firefox':
                folder = self.enter_context(tempfile.TemporaryDirectory(prefix='arkscope-midfill-package-', dir=Path.home() / 'snap/firefox/common'))
                self.rig.install_folder = Path(folder)
            folder = package(self.rig, self.browser, 'baseline')
            if self.browser == 'firefox': self._firefox(folder)
            else: self._chromium(folder)
            return self
        except BaseException:
            self.close()
            raise

    def _firefox(self, folder):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        profiles = self.enter_context(tempfile.TemporaryDirectory(prefix='arkscope-midfill-', dir=Path.home() / 'snap/firefox/common'))
        options = Options(); options.binary_location = '/snap/firefox/current/usr/lib/firefox/firefox'
        options.add_argument('-headless'); options.set_preference('network.proxy.type', 1)
        for scheme in ('http', 'ssl'):
            options.set_preference('network.proxy.' + scheme, '127.0.0.1')
            options.set_preference('network.proxy.' + scheme + '_port', 9)
        options.set_preference('network.proxy.no_proxies_on', '127.0.0.1,localhost')
        self.driver = webdriver.Firefox(options=options, service=Service(executable_path='/snap/bin/geckodriver',
            service_args=['--profile-root', profiles, '--allow-system-access'], log_output=str(self.rig.root / 'gecko.log')))
        self.callback(self.driver.quit)
        self.driver.set_context('chrome')
        # Selenium install_addon zips a directory into a different temporary path.
        # Load the actual folder, exactly like Load Temporary Add-on in Firefox.
        result = self.driver.execute_async_script('''
          const done=arguments[arguments.length-1];
          const file=Components.classes['@mozilla.org/file/local;1'].createInstance(Components.interfaces.nsIFile);
          file.initWithPath(arguments[0]);
          const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
          AddonManager.installTemporaryAddon(file).then(addon=>done({id:addon.id}),e=>done({error:String(e)}));
        ''', str(folder))
        assert 'error' not in result, result
        self.addon_id = result['id']
        identity = self.driver.execute_script('return JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))[arguments[0]]', self.addon_id)
        self.driver.set_context('content'); self.driver.set_script_timeout(30)
        self.url = f'moz-extension://{identity}/fixture.html'
        self.driver.get(self.url)

    def _chromium(self, folder):
        from playwright.sync_api import sync_playwright
        manager = self.rig.root / 'manager'; manager.mkdir()
        (manager / 'manifest.json').write_text(json.dumps({'manifest_version':3,'name':'Isolated reload controller','version':'1.0',
            'permissions':['management'],'background':{'service_worker':'manager.js'}}))
        (manager / 'manager.js').write_text('chrome.runtime.onInstalled.addListener(()=>{});')
        (manager / 'driver.html').write_text('<!doctype html><title>Reload controller</title>')
        pw = self.enter_context(sync_playwright())
        profile = self.rig.root / 'chromium'; (profile / 'Default').mkdir(parents=True)
        (profile / 'Default/Preferences').write_text(json.dumps({'extensions':{'ui':{'developer_mode':True}}}))
        browser = pw.chromium.launch_persistent_context(str(profile), headless=True, channel='chromium',
            args=[f'--disable-extensions-except={folder},{manager}', f'--load-extension={folder},{manager}',
                  '--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1;localhost'])
        self.callback(browser.close)
        controllers = [w for w in browser.service_workers if w.url.endswith('/manager.js')]
        controller = controllers[0] if controllers else browser.wait_for_event('serviceworker', predicate=lambda w: w.url.endswith('/manager.js'))
        self.manager = browser.new_page(); self.manager.goto(controller.url.rsplit('/',1)[0] + '/driver.html')
        entries = self.manager.evaluate('()=>chrome.management.getAll()')
        self.addon_id = next(e['id'] for e in entries if e['name'] == 'ArkScope Isolated Midfill Gate')
        self.url = f'chrome-extension://{self.addon_id}/fixture.html'
        self.page = browser.new_page(); self.page.goto(self.url)

    def call(self, command, **extra):
        message = dict(action='midfill_fixture', command=command, **extra)
        if self.browser == 'firefox':
            result = self.driver.execute_async_script('const done=arguments[arguments.length-1];browser.runtime.sendMessage(arguments[0]).then(done,e=>done({fixture_error:String(e)}));', message)
        else: result = self.page.evaluate('message=>chrome.runtime.sendMessage(message)', message)
        if (not result or 'fixture_error' in result) and self.browser == 'firefox':
            self.driver.set_context('chrome')
            print(self.driver.execute_script('return Services.console.getMessageArray().map(x=>x.message).filter(x=>x.includes("JavaScript Error"))'))
            self.driver.set_context('content')
        assert result and 'fixture_error' not in result, (command, result)
        return result

    def _addon(self, expression):
        self.driver.set_context('chrome')
        try:
            result = self.driver.execute_async_script('''
              const done=arguments[arguments.length-1],id=arguments[0];
              (async()=>{const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
                const addon=await AddonManager.getAddonByID(id);
            ''' + expression + ''';return {id:addon.id,enabled:addon.isActive,disabled:addon.userDisabled};
              })().then(done,e=>done({fixture_error:String(e)}));''', self.addon_id)
            assert 'fixture_error' not in result, result
            return result
        finally: self.driver.set_context('content')

    def replace(self, version):
        if self.browser == 'firefox':
            self.driver.get('about:blank')
            state = self._addon('await addon.disable()')
            assert state['disabled'] and not state['enabled'], state
        else:
            self.page.goto('about:blank')
            self.manager.evaluate('id=>chrome.management.setEnabled(id,false)', self.addon_id)
            assert not self.manager.evaluate('id=>chrome.management.get(id)', self.addon_id)['enabled']
        package(self.rig, self.browser, version)
        self.rig.collector = self.rig.new_collector if version == 'candidate' else self.rig.old_collector
        if self.browser == 'firefox':
            self._addon('await addon.reload()')
            state = self._addon('if (addon.userDisabled) await addon.enable()')
            assert state['enabled'] and state['id'] == self.addon_id, state
            self.driver.get(self.url)
        else:
            self.manager.evaluate('id=>chrome.management.setEnabled(id,true)', self.addon_id)
            assert self.manager.evaluate('id=>chrome.management.get(id)', self.addon_id)['enabled']
            self.page.goto(self.url)
        state = self.call('snapshot')
        assert state['version'] == version, state
        return state
