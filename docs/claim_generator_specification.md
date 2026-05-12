# Claim Generator — V1 Specification

This module generates an English patent-style claim draft for a single selected
claim, using the structured data already stored in the project: claim metadata,
linked elements, element definitions, and claim-local element ordering.

The generator is **template-driven**, not free-form. It does not invent claim
structure. Its job is to take the project's structured data and emit a
well-formed English claim that complies with EPO/PCT and USPTO conventions.

This document is the V1 contract. It defines what the generator does, what it
needs from the project, what it does not do, and the open product decisions
locked in for V1.

---

## 1. Generation modes

V1 supports four modes, selected by the existing `claim.claim_dependency_type`
and `claim.claim_category` columns:

1. Independent apparatus
2. Dependent apparatus
3. Independent method
4. Dependent method

No other modes are supported in V1. Mixed claim categories (hybrid claims) are
explicitly rejected.

---

## 2. Inputs

### From the selected claim
- `claim_id`
- `claim_number`
- `claim_dependency_type` — `independent` or `dependent`
- `claim_category` — `apparatus` or `method`
- `parent_claim_id` — required when dependent

### From the linked elements (`claim_element`, ordered by `order_index`)
For each linked element:
- `element_id`
- `element_name`
- `reference_number`
- `definition_text`
- `is_inventive` — boolean (added in V1, see §5)

### From the patent
- `patent_name` — used as the **main system name** in V1, see §6

---

## 3. Output contract

```python
class ClaimDraftResult(BaseModel):
    claim_id: int
    claim_number: int
    claim_dependency_type: str        # "independent" | "dependent"
    claim_category: str               # "apparatus" | "method"
    success: bool
    claim_text: str | None = None
    warning: str | None = None        # human-readable issue summary
    incomplete_elements: list[int] = []  # element_ids missing definitions
```

The generator **also writes** the produced text into `claim.claim_text`, so the
existing manual draft editor in the workspace shows the new draft on next load.

---

## 4. Templates

Template strings are fixed. The generator only fills the slots; it does not
rewrite definitions.

### 4.1 Independent apparatus (two-part / EPO Rule 43(1))

```
A[n] <main system name> (1) comprising
<Group A definition 1>, <Group A definition 2>, ..., <Group A definition N>;
characterized in that the <main system name> further comprises
<Group B definition 1>, ..., <Group B definition M>.
```

Rules:
- `Group A` = elements with `is_inventive = false`, ordered by `order_index`.
- `Group B` = elements with `is_inventive = true`, ordered by `order_index`.
- Each group's elements are joined by commas.
- Group A is closed by a semicolon before `characterized in that`.
- Group B is closed by a period.
- The main system name appears in the preamble and once after `characterized
  in that the`. It is **not** repeated at the end.
- If Group B is empty, the generator returns a `warning` and produces a
  single-part comprising-only claim. The user must mark at least one element
  as inventive for a true two-part claim — see §5.

### 4.2 Dependent apparatus

```
The <main system name> according to claim <X>, further comprising
<ordered element definition 1>, ..., <ordered element definition N>.
```

Rules:
- Definite article `The`, not `A[n]`.
- `<X>` comes from `parent_claim_id` → resolved to that claim's
  `claim_number`. Single parent only in V1 (see §7).
- Definitions ordered by `order_index`.
- Ends with a period after the last definition. Main system name is not
  repeated at the end.
- Inventive-step grouping does **not** apply to dependent claims. All linked
  elements appear in the `further comprising` list regardless of
  `is_inventive`.

### 4.3 Independent method

```
A method for <patent_name>, the method comprising:
- <step definition 1>,
- <step definition 2>,
- <step definition N>.
```

Rules:
- Each step is rendered as a dash-prefixed line ending with a comma. The last
  step ends with a period.
- The generator does **not** transform apparatus definitions into gerund
  form. The user must enter method-compatible (`-ing` form) definitions.
- If any linked element's `definition_text` does not contain a verb in
  `-ing` form, the generator emits a `warning` advising the user to revise.
  This is a heuristic check, not a hard block.
- Inventive-step grouping does not apply (method claims are single-part in
  V1).

### 4.4 Dependent method

```
The method according to claim <X>, further comprising:
- <step definition 1>,
- <step definition N>.
```

Same rules as 4.3, with the parent reference at the start.

---

## 5. Inventive-step marking (`is_inventive`)

Independent apparatus claims require the user to mark which elements
contribute to inventive step. This drives the Group A / Group B split in §4.1.

### Schema change
Add a column to `claim_element`:
```
is_inventive BOOLEAN NOT NULL DEFAULT FALSE
```
Migrated via Alembic. Existing rows default to `false`.

### UI flow
When the user clicks **Generate Claim Draft** for an independent apparatus
claim:
1. A modal opens listing the claim's linked elements in `order_index`.
2. Each row has a checkbox bound to its `is_inventive` value.
3. The user toggles checkboxes; on **Generate**, the new boolean values are
   PATCHed to the server, then the generator runs.

For other modes the modal is skipped — the generator runs directly.

---

## 6. Main system name (V1 decision)

The main system name in V1 is taken from `patent.patent_name`. Specifically:

- The patent name is used verbatim in the preamble as
  `A[n] <patent_name> (1)` for independent apparatus claims.
- For dependent apparatus claims, `The <patent_name>` is used.
- Method claims use `A method for <patent_name>` and `The method`.
- No reference number is generated for the main system if `patent_name`
  already contains parentheses; otherwise `(1)` is appended.

This is intentionally simple. A future version may introduce a dedicated
`claim.subject_name` or a project-level invention name field if patent_name
proves insufficient. V1 does not add that field.

---

## 7. Multiple parent claims — V1 boundary

V1 supports **single parent** only (the existing `parent_claim_id` FK).

- `according to claim X` is generated.
- `according to any one of claims X to Y` is **not** supported in V1.

A future version may introduce a `claim_parent` join table to support
multi-parent dependent claims. V1 does not add it.

---

## 8. Validation and incomplete-data behaviour

### Pre-generation checks
The generator validates inputs before producing text:

1. The claim has at least one linked element.
2. Every linked element has a non-empty `definition_text`.
3. For dependent claims, `parent_claim_id` is set and resolves to a real
   claim in the same patent.
4. For independent apparatus claims, at least one element has
   `is_inventive = true` (warning, not block — see §4.1).
5. For method claims, definitions appear to be in `-ing` form (warning,
   not block — see §4.3).

### Failure modes

| Condition | Default behaviour | With `force=true` |
|---|---|---|
| No linked elements | `success=false`, no draft | same — cannot generate from nothing |
| Some elements missing `definition_text` | `success=false`, list `incomplete_elements`, no draft | `success=true`, draft produced with `[MISSING DEFINITION]` placeholders, `warning` set |
| Dependent claim without parent | `success=false`, no draft | same — cannot resolve parent |
| Independent apparatus with no inventive marks | `success=true`, single-part draft, `warning` set | same |
| Method claim with non-gerund definitions | `success=true`, draft produced as-is, `warning` set | same |

The `force` flag is read from the request body. If absent, defaults to false.

---

## 9. API

### Request
```
POST /api/patents/{patent_id}/claims/{claim_id}/generate
Content-Type: application/json

{
  "force": false
}
```

The independent-apparatus inventive-step selection is sent **separately**
through the existing claim-element update endpoint before this call (driven
by the modal in §5). The generator reads `is_inventive` from the database;
it does not accept the selection in its own request body. This keeps the
generator side-effect free with respect to the inventive-step decision.

### Response
The `ClaimDraftResult` schema in §3, returned with HTTP 200.

### Side effects
On `success=true`, the generator writes the produced text to
`claim.claim_text` and updates `updated_at`. The textarea in the workspace
right panel reflects the new value on the next claim load.

---

## 10. Determinism

The generator is fully deterministic for a given input. Same claim + same
linked elements + same `is_inventive` flags + same definitions → same
output, byte-for-byte. There is no model call, no randomness, no
paraphrasing. This is intentional: the user must be able to predict the
output and trace each fragment back to a specific element definition.

The generator does not call the local or remote LLM for V1.

---

## 11. Out of scope for V1

The following are explicit non-goals in V1; they may appear in later
versions but are not part of this specification:

- Multi-parent dependent claims (`X to Y` ranges).
- Automatic gerund conversion of apparatus definitions for method claims.
- Auto-detection of inventive elements (always user-marked).
- Definition rewriting, paraphrasing, or style smoothing.
- Cross-claim consistency checks (e.g. element appears with the same
  reference number across claims).
- LLM-driven post-editing of the produced draft.
- Connector words inserted between definitions to improve readability
  (e.g. converting `A, B, C` into `A, B, and C`).

---

## 12. Acceptance criteria

V1 is considered complete when:

1. A user can generate an independent-apparatus claim that opens with the
   patent name, splits elements into `comprising` and `characterized in
   that` portions according to checkbox selections, and ends with a period
   after the last inventive element.
2. A user can generate a dependent-apparatus claim that opens with `The
   <patent_name> according to claim X, further comprising` and lists the
   linked element definitions in `order_index`.
3. Method modes produce dash-bulleted step lists, never with apparatus
   closings.
4. Validation paths return the documented `warning` and
   `incomplete_elements` values without crashing the generator.
5. The generated text is persisted to `claim.claim_text` and visible in
   the workspace draft editor on next load.
