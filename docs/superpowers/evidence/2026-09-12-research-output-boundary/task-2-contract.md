# Task 2 Source Inventory And Rulings

Source-only AST inventory: inventory-results.json, 54 registry definitions,
all resolved to source functions and return annotations. No imports/execution.
Plus API-bridge-only delegate_to_subagent -> dict, not a registry tool.

Policies:
- PUBLIC_TEXT: check_data_freshness, scan_alerts, get_economic_calendar,
  get_macro_value. Inspected implementations return human-readable prose,
  not JSON serialized into strings.
- PUBLIC_JSON: the remaining 50 registry definitions and bridge-only
  delegate_to_subagent. All return dict/list/Pydantic model (including nested
  public date/Decimal values). Full per-field financial domain schemas are not
  invented in this security slice. A dynamic public JSON map is explicit;
  additional closed validators must actually execute before admission.
- No implicit policy for unknown registrations. Builtins declare policies at
  their registration, not by broad method/category/field-name exemption.
- Direct API serializers resolve policies using create_default_registry (lazy
  construction, no DAL). Delegation is one explicit bridge contract. No
  output envelope can choose its own policy.
- Plain text policy must not auto-parse arbitrary JSON-looking prose. JSON
  policy rejects raw str instead of silently changing a broken object to text.
- Known native Pydantic BaseModel/date/datetime/finite Decimal get explicit
  normalization. Arbitrary model_dump duck types/repr/default=str are denied.
- Existing JSON list serialization differs: native list[dict] currently falls
  to Python str while OAuth uses JSON. Canonical JSON is the intended repair.

Two bypasses to fix in Task 2: OpenAI macro tool wrappers directly return text;
Anthropic execute_tool logs raw exceptions. Both must enter the shared boundary
or existing runtime diagnostic sanitizer, respectively. OpenAI SDK tool failure
callback also needs review: no raw rejected value should reach SDK default error
serialization. Do not change the runtime retry classifier.

Acceptance equality compares admitted JSON/text before independent reducer
budgets. Any reduced payload must still be secret-free because admission ran
first. Large structured pages are not granted SEC-specific reduction exceptions
in this slice; the paused feature task owns them separately.

Credential content policy: recursive explicit credential keys are denied, as
are exact matches against this execution's guard. Retain a narrowly defined
rejection for explicit authentication literals (Bearer and established provider
key prefixes), not the lossy probe's generic base64/length/mixed-case/PII rules.
This preserves the existing unknown sk-ant-api03 result safety owner without
letting ordinary words/numbers/cursors become credentials by shape alone.
This syntax rule rejects the entire tool result; it is never used to rewrite
successful fields or applied to arbitrary stream deltas. Document its exact
patterns and limits, including that arbitrary unknown secrets are not covered.

Use credential-key canonicalization that catches auth header spellings without
calling arbitrary __str__: ASCII lowercase plus separator normalization for
Authorization, Proxy-Authorization, X-Api-Key, api_key, access_token,
refresh_token, id_token, client_secret, password, private_key. Do not reject
token_usage or token_count. Numeric IDs are public unless an exact known secret
matches their emitted representation.

ResultPolicy validation contract: callable(value) -> bool must return literal
True; exceptions or mutated/invalid return values are typed failure. Domain
validator may not mutate the admitted normalized value unnoticed: either work
on a detached validated snapshot and revalidate or enforce immutability/digest
equivalence. Do not serialize callback exceptions or arbitrary validator repr.

Bounds: depth 64, at most 1,000,000 JSON nodes, total encoded output 32 MiB.
Keep existing compressor limits lower where configured; do not grow their
budgets. Count progressively during normalization/encoding, not after creating
unbounded duplicate representations. These are boundary safety limits, not
provider acquisition/file size ceilings.
