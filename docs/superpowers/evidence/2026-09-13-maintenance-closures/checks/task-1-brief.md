### Task 1: Close EIR-001

Files: `apps/arkscope-web/src/styles.css`, a focused
`apps/arkscope-web/src/retiredPageHeader.test.tsx`; existing PageHeader/primitives
only as read-only controls. Controller owns issue-register/evidence updates.

- [ ] Recount exact obsolete class selectors and search all actual frontend class
  consumers, including dynamic strings. `detailpage-head` is not `page-head`.
- [ ] Add a named selector-absence test before CSS deletion. Assert no exact
  `.page-head`/`.page-head-actions` selector in desktop or media rules, while
  rendering the real PageHeader and retaining `.detailpage-head` and current
  `.ui-page-header*` styles as nonempty positive controls.
- [ ] Record assertion RED, then delete only the obsolete desktop/mobile rules.
- [ ] Run focused and full frontend tests, typecheck/build, and desktop/mobile
  responsive visual checks with the real primitive and local CSS. No live App
  or provider; screenshots use a disposable browser and isolated fixture server.
- [ ] Restore an obsolete rule temporarily to prove the absence owner fails;
  restore reviewed bytes and rerun. Preserve declarations of all retained rules.
- [ ] Commit and independently review; controller closes EIR-001 with exact
  commit/results. Do not claim the whole CSS census queue closed.

