import fs from "node:fs";
import vm from "node:vm";

const [fixturePath, protocolPath, backgroundPath] = process.argv.slice(2);
const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

function protocolFixtureResults() {
  const context = vm.createContext({console});
  vm.runInContext(fs.readFileSync(protocolPath, "utf8"), context, {filename: protocolPath});
  return fixture.protocol_cases.map((entry) => {
    try {
      return {
        name: entry.name,
        ok: true,
        result: context.SAExtensionRunProtocol.deriveRunResult(entry.input),
      };
    } catch (error) {
      return {
        name: entry.name,
        ok: false,
        error_code: error && error.code ? error.code : "unexpected_error",
      };
    }
  });
}

function backgroundFixtureResults() {
  const imports = [];
  let protocolBeforeMessageRegistration = false;
  const context = vm.createContext({
    console,
    URL,
    setTimeout,
    clearTimeout,
    chrome: {
      runtime: {
        onMessage: {
          addListener() {
            protocolBeforeMessageRegistration = !!context.SAExtensionRunProtocol;
          },
        },
        onInstalled: {addListener() {}},
        onStartup: {addListener() {}},
        sendMessage() { return Promise.resolve(); },
        sendNativeMessage() {},
        lastError: null,
      },
      alarms: {onAlarm: {addListener() {}}},
      storage: {local: {get() {}, set() { return Promise.resolve(); }}},
      tabs: {},
      scripting: {},
    },
  });
  context.importScripts = (...names) => {
    for (const name of names) {
      imports.push(name);
      const path = new URL(name, `file://${backgroundPath}`).pathname;
      vm.runInContext(fs.readFileSync(path, "utf8"), context, {filename: path});
    }
  };
  vm.runInContext(fs.readFileSync(backgroundPath, "utf8"), context, {filename: backgroundPath});

  return {
    imports,
    protocol_before_message_registration: protocolBeforeMessageRegistration,
    alpha: fixture.background_cases.alpha.map((entry) => ({
      name: entry.name,
      result: context.buildAlphaPicksProtocolResult(entry.mode, entry.legacy_result),
    })),
    market: fixture.background_cases.market.map((entry) => ({
      name: entry.name,
      result: context.buildMarketNewsProtocolResult(entry.mode, entry.legacy_result),
    })),
  };
}

const output = backgroundPath ? backgroundFixtureResults() : protocolFixtureResults();
process.stdout.write(JSON.stringify(output));
