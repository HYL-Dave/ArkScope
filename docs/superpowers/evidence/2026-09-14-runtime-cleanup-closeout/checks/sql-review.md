1. **[P2] Invalidate bindings stored outside `ast.Name`** ([repository_inventory.py](/tmp/arkscope-research-output-boundary/tests/repository_inventory.py:150)). The binding collector misses pattern captures (`MatchAs.name`, `MatchStar.name`, `MatchMapping.rest`) and `ExceptHandler.name`. For example:

   ```python
   TABLE = "before"
   match "after":
       case TABLE:
           pass
   DDL = f"CREATE TABLE {TABLE}(id TEXT)"
   ```

   Source tracing shows this emits static `CREATE TABLE before(id TEXT)`, although the capture binds `TABLE` to `"after"`. Capturing `KINDS`, `quoted`, or `sorted` likewise leaves stale enum/helper evidence trusted. Invalidate these syntactic binders even without interpreting their control flow, and add negative controls for pattern/exception rebinding.

2. **[P2] Reject same-assignment rebinding before using the entry snapshot** ([repository_inventory.py](/tmp/arkscope-research-output-boundary/tests/repository_inventory.py:259)). Every nested f-string uses the context from before its entire module assignment, even when an earlier eagerly evaluated sibling explicitly rebinds a dependency:

   ```python
   TABLE = "before"
   DDLS = [(TABLE := "after"), f"CREATE TABLE {TABLE}(id TEXT)"]
   ```

   Source tracing shows the f-string is marked `dynamic=False` with table `before`, not `after`. The collector sees the walrus store but invalidates only the context for subsequent statements. Conservatively reject relevant intra-assignment stores, or track their evaluation order; add a same-statement regression alongside the existing later-statement snapshot test. Both cases can inject fabricated tables/read witnesses into the SQLite union despite `deletion_authorized` remaining false.
