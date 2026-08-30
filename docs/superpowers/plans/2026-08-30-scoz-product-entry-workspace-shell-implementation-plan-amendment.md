# Product Entry & Workspace Shell Implementation Plan — Approval Amendment

**Status:** Approved for implementation  
**Approved via:** PR #93 merged to `main` as `b341c4327b945df347804bfddabe5677a6887946`  
**Applies to:** `docs/superpowers/plans/2026-08-30-scoz-product-entry-workspace-shell-implementation-plan.md`  
**Spec authority remains:** `docs/superpowers/specs/2026-08-29-scoz-product-entry-workspace-shell-implementation-spec.md`

## Authority

This amendment is intentionally small and does not replace the 1730-line implementation plan. The main plan and this amendment together form the approved execution plan for the corrective Product Entry & Workspace Shell implementation.

Where the main plan still says `Draft for user approval`, this amendment supersedes that status: the plan is approved for implementation after this amendment is merged.

Where Task 4 or Task 5 of the main plan is silent about the transition case below, the requirements in this amendment are mandatory and take precedence. All other task ordering, file boundaries, TDD steps, non-goals, verification gates and PR6/PR7 invariants in the main plan remain unchanged.

No production code, database schema, API contract or frontend behavior is changed by this amendment.

---

## Mandatory Task 4 addition — preserve query readiness when ProductSnapshot is missing

The implementation exists specifically because Product ownership/data readiness and ProductSnapshot readiness are independent. Therefore Task 4 must include RED service coverage for an owned Product that has a canonical Ozon identity and current ProductQuerySnapshot evidence but **no ProductSnapshot**.

Add at least these two service cases in `tests/test_product_workspace_service.py` before implementing/finalizing `ProductWorkspaceService.get_context()`:

### Case A — query data exists, no saved relevant-query selection

Seed:

```text
Product.is_owned = true
canonical unscoped Ozon identity exists
ProductSnapshot = absent
current ProductQuerySnapshot period exists
product_relevant_queries rows = 0
benchmark current revision = absent
```

Required assertions:

```python
assert context.product.product_data_status is ProductDataStatus.MISSING
assert context.product.title is None
assert context.product.report_generated_on is None
assert context.queries.readiness is RelevantQueryReadiness.EMPTY_SELECTION
assert context.queries.latest_period is not None
assert context.queries.selected_count == 0
assert context.benchmark.status is WorkspaceBenchmarkStatus.NOT_CONFIGURED
```

### Case B — query data exists and relevant-query selection is saved

Seed the same Product state, but add at least one saved relevant query.

Required assertions:

```python
assert context.product.product_data_status is ProductDataStatus.MISSING
assert context.queries.readiness is RelevantQueryReadiness.READY
assert context.queries.latest_period is not None
assert context.queries.selected_count > 0
```

The key invariant is:

```text
ProductSnapshot missing
!=
query data missing
```

`ProductWorkspaceService.get_context()` must compose Product readiness and query readiness independently. It must never derive `NO_OWN_QUERY_DATA` merely because `ProductDataStatus == MISSING`.

The existing identity-only/no-query case in Task 4 remains required and must still map to `NO_OWN_QUERY_DATA`.

---

## Mandatory Task 5 addition — HTTP contract for missing ProductSnapshot with existing query data

Task 5 must mirror the same transition invariant at the API boundary in `tests/test_product_workspace_api.py`.

Add an owned canonical Ozon Product with:

```text
ProductSnapshot absent
current ProductQuerySnapshot period present
```

and verify `GET /api/products/{product_id}/workspace-context` returns HTTP 200 with independent states.

At minimum, prove one `EMPTY_SELECTION` case:

```json
{
  "product": {
    "product_data_status": "MISSING",
    "title": null,
    "report_generated_on": null,
    "report_window_days": null,
    "imported_at": null
  },
  "queries": {
    "readiness": "EMPTY_SELECTION",
    "selected_count": 0
  },
  "benchmark": {
    "status": "NOT_CONFIGURED"
  }
}
```

Also prove the saved-selection variant either in the same API test or a second focused test:

```text
product.product_data_status == "MISSING"
queries.readiness == "READY"
queries.selected_count > 0
```

Do not require a ProductSnapshot to expose query readiness. Do not fabricate Product title/seller/brand/report freshness for this case.

The existing API test for a truly identity-only Product with no query evidence remains required and must still return:

```text
product.product_data_status == MISSING
queries.readiness == NO_OWN_QUERY_DATA
```

---

## Execution gate after this amendment

After merge, Codex implementation must read, in order:

1. the approved Product Entry & Workspace Shell Implementation Spec;
2. the main Product Entry & Workspace Shell Implementation Plan;
3. **this amendment**.

Then execute Tasks 1–11 in the original dependency order, with the additional RED cases above inserted into Task 4 and Task 5.

No implementation branch should reinterpret these added tests as optional cleanup. They are acceptance coverage for the central ownership-vs-data-readiness invariant of the corrective PR.
