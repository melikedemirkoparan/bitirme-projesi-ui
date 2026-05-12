
# Claim Generator Specification

## Purpose
This module is responsible for generating English patent-style claim draft text for a selected claim in the workspace.

It uses:
- the selected claim's metadata
- the claim category
- the claim dependency type
- the ordered linked elements in that claim
- the generated / saved element definitions already stored in the system
- parent-claim relationship data for dependent claims

The generator does **not** invent a new claim structure from scratch.

Its main role is to:
- read the claim-local ordered element structure
- concatenate the selected element definitions in the correct order
- apply the appropriate claim pattern depending on:
  - independent vs dependent
  - apparatus vs method
- produce a patent-style English claim draft compliant with EPO/PCT and USPTO standards

The system should stay conservative and template-driven.
This is a structured drafting module, not an open-ended free writing module.

---

## Core principle
The claim generator is driven by the **claim-local ordered element list**.

The order of the linked elements inside a claim is already stored through:

- `claim_element.order_index`

This order must be treated as the primary composition order.

So when generating a claim:
- fetch the linked elements of the selected claim
- sort by `order_index`
- read their saved definitions in that exact order
- concatenate them into the claim draft according to the applicable claim pattern

---

## Input sources

### Claim-level input
For the selected claim, the generator must read:

- `claim_id`
- `claim_number`
- `claim_dependency_type`
  - `independent`
  - `dependent`
- `claim_category`
  - `apparatus`
  - `method`
- `parent_claim_id` or parent-claim relation info
- linked elements of the claim
- `order_index` of each linked element

### Element-level input
For each linked element in the selected claim, the generator must read:

- `element_id`
- `element_name`
- `reference_number`
- `definition_text`

Only elements with non-empty `definition_text` should be usable for final generation.

If a linked element has no saved definition:
- the claim should be treated as incomplete
- generation should either stop with a structured warning
- or produce a draft marked as incomplete, depending on product decision

---

## Claim generation modes
The generator has different behavior depending on:

1. independent vs dependent
2. apparatus vs method

These two dimensions must be handled explicitly.

---

# 1. Independent apparatus claim generation

## Goal
Generate an English independent apparatus claim using the EPO two-part form (Rule 43(1) EPC):
- a `comprising` portion for non-inventive / background elements (Group A)
- a `characterized in that` portion for inventive-step-contributing elements (Group B)

This maps directly to the Turkish patent two-part structure:
- `içeren` → `comprising`
- `ile karakterize edilen` → `characterized in that`

---

## Two-part claim structure

### Part 1 — comprising (Group A elements)
Group A elements are concatenated into the `comprising` portion of the claim.
These are the background / non-inventive elements that provide context for the invention.

### Part 2 — characterized in that (Group B elements)
Group B elements are concatenated into the `characterized in that` portion of the claim.
These are the elements that contribute to inventive step.

---

## Independent apparatus template

```
<A[n] main system name> comprising
<Group A definition 1>, <Group A definition 2>, ..., <Group A definition N>;
characterized in that the <main system name> further comprises
<Group B definition 1>, <Group B definition 2>, ..., <Group B definition N>.
```

**Rules:**
- The main system name appears **only at the opening** of the claim (preamble).
- The claim ends with the last Group B element definition followed by a **period**.
- The system name is **not repeated at the end** of the claim.
- Group A definitions are separated by commas and closed with a semicolon before `characterized in that`.
- Group B definitions are separated by commas and closed with a period.

**Example output:**

> An adjustable equipment mounting system (1) comprising a body (G), an intermediate piece (2) located on the body (G) and extending outwardly therefrom, a cylindrical tube (3) extending in at least two directions and/or having a bend attached to the intermediate piece (2) in a removable manner, at least one equipment (E) attached to the tube (3) in a removable manner, a first fastener (4) securing the tube (3) to the intermediate piece (2); characterized in that the adjustable equipment mounting system (1) further comprises a protrusion (2a) passing through the interior of the tube (3) enabling the tube (3) to be mounted to the intermediate piece (2) and rotated about its own axis, a first adjustment region (5) located in the portion of the tube (3) passing through the protrusion (2a) enabling angular position adjustment of the equipment (E).

---

## Inventive-step subset handling — checkbox UI

The two-part structure requires the user to explicitly mark which elements contribute to inventive step before generation.

### Behavior
When the user clicks **Claim Draft** for an independent apparatus claim, the UI shows a checkbox group:

**Select the elements that contribute to inventive step**

The list is populated from the claim's linked elements.

- Unchecked elements → Group A → `comprising` portion
- Checked elements → Group B → `characterized in that` portion

Both groups preserve their internal `order_index` ordering.

This step is mandatory for independent apparatus claims and must be completed before the generator proceeds.

---

## Main-system naming rule
The main claimed subject must come from system-level claim metadata — not guessed freely.

Examples:
- `an adjustable equipment mounting system (1)`
- `an optical system (1)`
- `a release mechanism (1)`

---

## Independent apparatus output requirements
- Preserve `order_index` within each group
- Preserve element `definition_text` as saved — do not paraphrase
- Group A → `comprising` portion, definitions comma-separated, closed with semicolon
- Group B → `characterized in that the <system> further comprises` portion, definitions comma-separated, closed with period
- System name appears in preamble only — **never repeated at the end**
- Remain in English

---

# 2. Dependent apparatus claim generation

## Goal
Generate an English dependent apparatus claim compliant with EPO/USPTO standards.

In English patent practice, dependent claims begin with the parent claim reference, then add further limitations.

---

## Dependent apparatus template

```
The <main system name> according to claim <X>, further comprising
<ordered element definition 1>, <ordered element definition 2>, ..., <ordered element definition N>.
```

For multiple parent claims:

```
The <main system name> according to any one of claims <X> to <Y>, further comprising
<ordered element definitions>.
```

**Rules:**
- The parent claim reference comes **first** — this is mandatory in English patent practice.
- `The` (definite article) is used in dependent claims, not `A[n]`.
- The claim ends with the last element definition followed by a **period**.
- The system name is **not repeated at the end**.

**Example output:**

> The adjustable equipment mounting system (1) according to claim 1, further comprising a second adjustment region (9) located on the adapter (6) enabling final pitch angle adjustment of the equipment (E) about the second adjustment axis (3b).

---

## Primary logic
1. fetch the selected claim's ordered linked elements
2. sort by `order_index`
3. open with: `The <system name> according to claim <X>, further comprising`
4. concatenate element definitions in order, comma-separated
5. close with a period

---

## Parent-claim reference rule
The system stores dependency information. The generator must use it directly.

- one parent claim → `according to claim X`
- multiple parent claims → `according to any one of claims X to Y`

The generator must not guess dependency ranges if structured dependency data exists.

---

## Dependent apparatus output requirements
- Parent claim reference at the beginning, not the end
- Definite article `The` in opening
- Concatenate ordered element definitions
- Preserve claim-local `order_index`
- End with a period after the last definition
- System name not repeated at the end

---

# 3. Method claim generation

## Critical rule — no hybrid claims

A method claim must begin and end as a method claim.
An apparatus claim must begin and end as an apparatus claim.

**Mixing method steps (gerund/-ing form) with an apparatus closing is a hybrid claim and will be rejected by EPO and USPTO.**

This system supports two valid interpretations for what was previously called "method-style":

---

## Option A — True method claim

If the claim category is `method` and the intent is a standalone method claim:

### Independent method template

```
A method for <purpose/field>, the method comprising:
- <step definition 1>,
- <step definition 2>,
- <step definition N>.
```

### Dependent method template

```
The method according to claim <X>, further comprising:
- <step definition 1>,
- <step definition N>.
```

**Rules:**
- Each step is rendered as a dash-prefixed line ending with a comma.
- The last step ends with a period.
- The claim ends after the last step — no apparatus name at the end.
- `definition_text` must be in gerund form (e.g., `positioning the tube...`, `rotating the tube...`). The generator does not transform apparatus definitions into gerund form — the user must enter method-compatible definitions.

**Example output:**

> A method for mounting equipment on a body, the method comprising:
> - positioning the tube (3) along the first adjustment axis (3a) so as to contact the abutment surface (2b) and attaching it to the intermediate piece (2),
> - rotating the tube (3) about the first adjustment axis (3a) from the first adjustment region (5) to perform roll, pitch and yaw angle adjustments of the equipment (E),
> - rotating the second adjustment region (9) together with the adapter (6) about the second adjustment axis (3b) to perform the final pitch angle adjustment of the equipment (E).

---

## Option B — Apparatus claim with functional language

If the intent is an apparatus claim but element definitions describe actions/functions, the correct English form uses `configured to` rather than gerund steps.

### Template

```
<A[n] main system name> comprising
<element name> configured to <function>, <element name> configured to <function>, ...;
characterized in that the <main system name> further comprises
<element name> configured to <function>.
```

**Example:**

> An adjustable equipment mounting system (1) comprising a tube (3) configured to be positioned along the first adjustment axis (3a) so as to contact the abutment surface (2b); characterized in that the adjustable equipment mounting system (1) further comprises a first adjustment region (5) configured to enable angular position adjustment of the equipment (E) about the first adjustment axis (3a).

---

## Generator behavior for method category

When `claim_category = method`:
- the generator must not append an apparatus name at the end
- the generator must not produce a hybrid claim
- the claim must open and close as a method claim
- each step is rendered as a dash-prefixed line

When `claim_category = apparatus` and definitions contain functional language:
- use `configured to` phrasing within the apparatus template
- do not use gerund step format

---

# 4. Claim generator workflow

## High-level generation flow
When the user clicks **Claim Draft** for a selected claim:

### Step 1 — Load claim context
Load:
- claim metadata
- dependency type
- category
- parent claim info
- linked elements
- `order_index`

### Step 2 — Validate claim completeness
Check:
- are there linked elements?
- do all linked elements have non-empty `definition_text`?

If not:
- return a structured warning or incomplete draft state

### Step 3 — For independent claims, show inventive-step checkbox UI
If the claim is `independent` (apparatus or method):
- show checkbox list populated from linked elements
- user marks which elements contribute to inventive step
- confirmed selection is required before proceeding

### Step 4 — Choose generation mode
Branch by:
- independent apparatus
- dependent apparatus
- independent method
- dependent method

### Step 5 — Generate draft text
Apply the appropriate template and concatenate ordered definitions.

### Step 6 — Return structured result
Return:
- generated claim text
- claim id
- claim number
- mode used
- warning flags if any

---

# 5. Structured output contract

## Output model

```python
class ClaimDraftResult(BaseModel):
    claim_id: int
    claim_number: int
    claim_dependency_type: str  # "independent" | "dependent"
    claim_category: str         # "apparatus" | "method"
    success: bool
    claim_text: str | None = None
    warning: str | None = None
```
