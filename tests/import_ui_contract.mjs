import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const source = await readFile(new URL("../frontend/assets/js/import_ui.js", import.meta.url), "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const importUi = context.globalThis.ScozImportUi;

assert.ok(importUi);
assert.equal(importUi.classifyFilename("ozon_products", "analytics_report_2026-08-25_19_54.xlsx").kind, "MATCH");
assert.deepEqual(
  { ...importUi.classifyFilename("ozon_products", "queries_report-2026-08-25_19_48.xlsx") },
  { kind: "KNOWN_OTHER", detectedSource: "query_metrics" },
);
assert.deepEqual(
  { ...importUi.classifyFilename("query_metrics", "analytics_report_2026-08-25_19_54.xlsx") },
  { kind: "KNOWN_OTHER", detectedSource: "ozon_products" },
);
assert.equal(importUi.classifyFilename("search_visibility", "explainer_report_25-08-2026_19-45-21.xlsx").kind, "MATCH");
assert.equal(importUi.classifyFilename("seller_queries", "seller-queries_27.07-23.08.2026_created_2026-08-25_19-46.xlsx").kind, "MATCH");
assert.equal(importUi.classifyFilename("ozon_products", "renamed.xlsx").kind, "UNKNOWN");
assert.equal(importUi.classifyFilename("ozon_products", "ANALYTICS_REPORT_TEST.XLSX").kind, "MATCH");

for (const [seconds, expected] of [[0, "00:00"], [9, "00:09"], [59, "00:59"], [60, "01:00"], [65, "01:05"], [754, "12:34"]]) {
  assert.equal(importUi.formatElapsed(seconds), expected);
}
assert.match(importUi.workingMessage(29), /^Импортируем/);
assert.match(importUi.workingMessage(30), /больше обычного/);

console.log("import UI contract: PASS");
