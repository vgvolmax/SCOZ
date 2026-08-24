(function (root) {
  "use strict";

  function create() {
    return { selectedProductIds: new Set(), metadataByProductId: new Map() };
  }

  function rememberCandidates(state, items) {
    for (const item of items || []) state.metadataByProductId.set(item.product_id, item);
  }

  async function loadWorkspace(loadRelevance, loadBenchmark, loadCandidates) {
    const [relevance, benchmark] = await Promise.all([loadRelevance(), loadBenchmark()]);
    const state = create();
    const members = benchmark?.current_revision?.members || [];
    state.selectedProductIds = new Set(members.map((item) => item.product_id));
    rememberCandidates(state, members);
    const candidates = relevance?.selected_count > 0 ? await loadCandidates() : null;
    rememberCandidates(state, candidates?.items);
    return state;
  }

  root.ScozCompetitorState = { create, rememberCandidates, loadWorkspace };
})(typeof window === "undefined" ? globalThis : window);
