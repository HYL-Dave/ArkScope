const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {JSDOM} = require('jsdom');

module.exports = async function mountFinancialPopup(extensionDir, dispatch) {
  const dom = new JSDOM(fs.readFileSync(path.join(extensionDir, 'popup.html'), 'utf8'), {
    url: 'moz-extension://financial-fixture/popup.html', runScripts: 'outside-only',
  });
  dom.window.chrome = {
    runtime: {sendMessage(message, callback) { Promise.resolve(dispatch(message)).then(callback); }},
    storage: {onChanged: {addListener() {}}},
  };
  const settle = async () => {
    for (let i = 0; i < 4; i++) await new Promise(resolve => setTimeout(resolve, 0));
  };
  vm.runInContext(fs.readFileSync(path.join(extensionDir, 'popup_company_refresh.js'), 'utf8'), dom.getInternalVMContext());
  await settle();
  return {document: dom.window.document, Event: dom.window.Event, settle, close: () => dom.window.close()};
};
