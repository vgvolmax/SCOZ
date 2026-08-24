import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const source = await readFile(new URL("../frontend/assets/js/competitor_state.js", import.meta.url), "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const stateTools = context.globalThis.ScozCompetitorState;

for (const delays of [{ relevance: 0, benchmark: 20 }, { relevance: 20, benchmark: 0 }]) {
  const events = [];
  const later = (name, delay, value) => new Promise((resolve) => setTimeout(() => { events.push(name); resolve(value); }, delay));
  const result = await stateTools.loadWorkspace(
    () => later("relevance", delays.relevance, { selected_count: 1 }),
    () => later("benchmark", delays.benchmark, { current_revision: { members: [{ product_id: 7, ozon_product_id: "700" }] } }),
    () => { events.push("candidates"); return Promise.resolve({ items: [{ product_id: 7 }] }); },
  );
  assert.equal(events.at(-1), "candidates");
  assert.deepEqual([...result.selectedProductIds], [7]);
}

const state = stateTools.create();
stateTools.rememberCandidates(state, [{ product_id: 8, ozon_product_id: "800" }]);
state.selectedProductIds.add(8);
stateTools.rememberCandidates(state, [{ product_id: 9, ozon_product_id: "900" }]);
assert.equal(state.metadataByProductId.get(8).ozon_product_id, "800");
assert.deepEqual([...state.selectedProductIds], [8]);
console.log("competitor state contract: PASS");
