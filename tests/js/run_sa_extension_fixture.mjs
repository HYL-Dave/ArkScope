import fs from "node:fs";
import vm from "node:vm";
import { JSDOM } from "jsdom";

const [fixturePath, ...scriptPaths] = process.argv.slice(2);
const dom = new JSDOM(fs.readFileSync(fixturePath, "utf8"), {
  url: "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy",
  runScripts: "outside-only",
});
Object.defineProperty(dom.window.HTMLElement.prototype, "innerText", {
  get() { return this.textContent || ""; },
});
let result;
for (const scriptPath of scriptPaths) {
  result = vm.runInContext(fs.readFileSync(scriptPath, "utf8"), dom.getInternalVMContext());
}
process.stdout.write(JSON.stringify(result));
