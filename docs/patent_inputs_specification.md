# Patent Inputs Specification

## Purpose
This document describes the structured input sources used by the patent drafting system.

Its purpose is to explain:
- what input data the system receives
- how each input type is structured
- what kind of information each field contains
- how these inputs may later support downstream modules such as element extraction, claim drafting, and definition generation

This document focuses on the **input structure**, not on generation logic.

---

## Main input groups
The current system is designed around three main structured project inputs:

1. `Invention_disclosure`
2. `Research_report`
3. `Inventor_QA`

Each input type stores a different kind of patent-related evidence.

---

## 1. Invention_disclosure

### Purpose
The `Invention_disclosure` input captures the earliest structured invention description entered during project creation.

It provides:
- prior art context
- known problems and limitations
- the closest known patents
- the invention's novel features
- optionally, visual/material notes if later included

This input is especially useful for:
- understanding the invention motivation
- identifying novelty signals
- identifying candidate technical functions
- identifying differences from the known state of the art

---

### Fields

#### `prior_art_and_problems`
This field contains a free-text explanation of:
- the known state of the art
- the starting patent or baseline system
- the limitations of earlier approaches
- the problem the new invention is trying to solve

This field is usually descriptive and explanatory.

#### Example content style
A typical entry may describe:
- an earlier patent used as the starting point
- missing technical capabilities in prior art
- why the new invention is needed
- what improvement the invention aims to provide

#### Example
> Patent US5940222 was taken as the starting point. However, this and similar patents do not include multiple wavelength capability. Therefore, an optical system design was planned that can detect visible, near infrared (NIR), mid-wave infrared (MWIR), and long-wave infrared (LWIR) wavelengths, enabling clear target observation under all weather conditions and providing environmental awareness through observation at different angles. The system shares some similarities with ASELSAN's CATS system, but the present invention differs in design details, calculations, field-of-view characteristics, and wavelength diversity. One major advantage of LWIR is that it provides long-range situational awareness that other wavelengths cannot provide, especially for air-to-air superiority purposes.

---

#### `closest_prior_patents`
This field contains a list of the patent numbers or identifiers considered closest to the invention.

It is typically short and list-like.

#### Example content style
A typical entry may contain:
- one patent number per line
- a short list of prior patents
- no long explanation required

#### Example
- `US5940222`
- `US4714307`
- `US4523816`
- `US4235508`
- `US4240702`

This field is especially useful for:
- prior art grounding
- patent comparison workflows
- novelty analysis support

---

#### `novel_features`
This field contains the invention's novel features, usually as structured feature/element statements.

It often appears as a numbered or itemized list.

This field is especially important because it directly expresses the invention's differentiating technical points.

#### Example content style
A typical entry may list invention features as:
- `Feature 1`
- `Feature 2`
- `Feature 3`

or in the Turkish workflow:
- `Unsur 1`
- `Unsur 2`
- `Unsur 3`

#### Example
> Feature 1 – Multiple wavelengths  
> Feature 2 – Multiple zoom settings  
> Feature 3 – The optical path is shortened by mathematically positioning mirrors so as to create an intermediate image plane.

This field is especially useful for:
- candidate function extraction
- invention-difference analysis
- later claim support
- later definition generation support

---

#### `figures_and_media_notes` *(optional / future-ready)*
This field is intended for notes related to:
- figures
- drawings
- images
- visual explanations
- media references

This field may not yet be actively used in the current version, but it is part of the broader invention disclosure structure and may be important later.

It can support:
- geometry understanding
- structural interpretation
- visual reference alignment

---

### Observations about Invention_disclosure
Among all invention disclosure fields:

- `prior_art_and_problems` is especially useful for:
  - invention motivation
  - problem framing
  - function-level intent
  - novelty context

- `closest_prior_patents` is especially useful for:
  - prior art grounding
  - patent comparison support
  - later retrieval alignment

- `novel_features` is especially useful for:
  - direct extraction of invention-defining technical candidates
  - function candidate generation
  - structured invention summarization

- `figures_and_media_notes` is especially useful for:
  - geometry support
  - visual grounding
  - later structural interpretation

---

## Input design rule
Input fields should be stored as structured project data exactly as entered by the user, without forcing premature transformation at the storage stage.

Later modules may:
- summarize them
- extract candidates from them
- rank evidence from them
- combine them with retrieval outputs

But the raw structured input should remain available as a source of truth.

## 2. Research_report

### Purpose
The `Research_report` input captures the structured patentability and prior-art analysis prepared for the invention.

It provides:
- a high-level technical and patentability summary
- the purpose of the research work
- classification and keyword information
- detailed element-to-prior-patent comparison

This input is especially useful for:
- technical summarization
- function-level evidence
- novelty/inventive-step interpretation
- prior-art comparison
- identifying structured support for definition generation

Compared to the invention disclosure, the research report is typically more analytical, more comparative, and more patent-focused.

---

### Fields

#### `executive_summary`
This field contains a high-level summary of:
- the known technical state
- why the invention is useful or advantageous
- the main technical elements of the invention
- an initial novelty / inventive-step assessment

It is usually one of the densest and most informative fields in the entire input set.

#### Example content style
A typical entry may explain:
- why a certain optical or technical architecture is beneficial
- what mission/environmental needs it addresses
- which core invention features are present
- an initial legal/technical conclusion regarding novelty and inventive step

#### Example
> In the known state of the art, catadioptric lenses can be used to provide extremely long focal lengths while requiring only a relatively short physical length compared to other optical system types. Since protrusions on the aircraft surface are aerodynamically undesirable and heavy structures are not preferred, catadioptric lenses are suitable for aircraft use. Their use provides packaging and weight advantages for the optical system. For an aircraft, it would be highly advantageous to realize an optical system that can operate effectively in different mission profiles such as air-to-air and air-to-ground, can provide effective imaging under different environmental conditions such as daylight and darkness, and can detect multiple wavelength bands (visible, NIR, MWIR, LWIR), thereby enabling clear target observation and environmental awareness at different viewing angles.  
>
> With the present invention, such an optical system has been realized. The invention includes the following features:  
> 1. Use of a catadioptric optical system in which the first and second mirrors are positioned at suitable locations and angles to obtain an intermediate image plane, thereby shortening the optical path and facilitating wavelength separation.  
> 2. Use of a movable lens group to provide optical zoom and Multi FoV (Field of View).  
> 3. Use of a rotatable beam splitter cube or filter positioned behind the intermediate image plane to obtain multiple wavelength outputs.  
>
> According to the European Patent Convention Articles 54 and 56, the first and second features do not contain novelty or inventive step, while the third feature, when evaluated together with the first and second, contains novelty but not inventive step. Final assessment will be made by the IP board.

#### Why it matters
This field is especially useful for:
- overall invention understanding
- candidate technical function extraction
- high-level geometry/context reasoning
- identifying what the system is fundamentally trying to achieve

---

#### `search_strategy`
This field contains the purpose and scope of the research effort.

In some research reports, this section may be very short and mostly state the purpose of the patentability study.
In other cases, it may also include search notes or search logic.

#### Example content style
A typical entry may explain:
- why the study was conducted
- what invention was assessed
- that the purpose was patentability analysis

#### Example
> The purpose of this study is the patentability analysis of the invention disclosure titled “Catadioptric Multi FoV and Multi Wavelength Optical System”.

#### Why it matters
This field is usually not the strongest technical source for definition generation, but it is useful for:
- confirming the invention scope
- clarifying the objective of the report
- keeping the system aligned with the correct invention identity

---

#### `classification_and_keywords`
This field contains:
- technical classification codes
- keyword strategy
- domain-specific terminology used during patent research

It is often list-like and highly structured.

#### Example content style
A typical entry may include:
- CPC / IPC-style optical system classes
- zoom, catadioptric, beam splitter, multispectral terms
- domain and mechanism descriptors

#### Example
> G02B17/08: Catadioptric systems  
> G02B15/00: Optical objectives with means for varying magnification  
> G02B15/14: By axial movement of one or more lenses or groups of lenses  
> G02B7/04: Mechanism for focusing or varying magnification  
> G02B17/0896: Catadioptric systems with variable magnification or multiple imaging planes, including multispectral systems  
> G02B27/149: Beam splitting or combining systems using crossed beamsplitting surfaces  
> G02B13/146: Optical objectives for infra-red or ultra-violet radiation with corrections for multiple wavelength bands

#### Why it matters
This field is especially useful for:
- domain understanding
- retrieval support
- invention classification
- identifying technical vocabulary relevant to the invention

It is usually more useful for domain alignment and retrieval than for direct final definition text.

---

#### `element_patent_analysis`
This field contains the detailed comparison between invention features/elements and prior patent documents.

It is usually the most comparison-heavy and evidence-rich field in the research report.

This field often includes:
- a specific invention feature
- one or more prior patent references
- quotations or paraphrases of the prior patent mechanism
- a novelty / inventive-step interpretation

#### Example content style
A typical entry may look like:
- Feature 1 compared against one patent
- Feature 2 compared against the same or another patent
- Feature 3 compared against another prior-art mechanism
- conclusion about whether novelty or inventive step is present

#### Example
> Feature 1 – Use of a catadioptric optical system in which the first and second mirrors are positioned appropriately to obtain an intermediate image plane, shorten the optical path, and facilitate wavelength separation.  
>  
> Patent US5940222A describes catadioptric zoom lens assemblies. It teaches a forward-facing primary mirror and a rear-facing secondary mirror that form an intermediate image in front of the primary mirror. A zoom relay lens group is placed optically behind the intermediate image and includes a fixed field lens subgroup and movable lens subgroups.  
>
> Feature 2 – Use of a movable lens group to provide optical zoom and Multi FoV.  
>  
> Patent US5940222A also teaches movable lens groups that provide both focal length variation and focus adjustment.  
>
> Feature 3 – Use of a rotatable beam splitter cube or filter behind the intermediate image plane to obtain multiple wavelengths.  
>  
> Patent US9857585B2 describes a rolling beam splitter optical switching mechanism capable of directing reflected electromagnetic radiation toward different detectors. The beam splitter cube can be rotated to route radiation toward different cameras.  
>
> Based on the prior-art documents, Feature 3, when evaluated together with Features 1 and 2, contains novelty but not inventive step.

#### Why it matters
This field is especially useful for:
- feature-by-feature functional reasoning
- geometry and structure clues from prior-art comparisons
- identifying whether a candidate function is already known or framed as novel
- grounding definition generation in comparative technical evidence

Among all research report fields, this is often one of the most valuable for later definition-generation modules.

---

### Observations about Research_report
Among all research report fields:

- `executive_summary` is especially useful for:
  - condensed invention understanding
  - function-level summarization
  - identifying key technical features
  - initial novelty/inventive-step framing

- `search_strategy` is especially useful for:
  - invention scope confirmation
  - report-purpose clarification
  - contextual alignment

- `classification_and_keywords` is especially useful for:
  - domain understanding
  - retrieval support
  - technical vocabulary alignment
  - search/domain grounding

- `element_patent_analysis` is especially useful for:
  - detailed technical comparison
  - feature-level evidence
  - identifying structural and functional clues
  - novelty-aware interpretation for downstream modules

---

## Input design rule for Research_report
Research report fields should be stored as structured project inputs exactly as entered, without forcing premature compression into a single summary.

Later modules may:
- extract feature candidates
- compare evidence strength
- derive functional interpretations
- use classification fields for domain support

But the original structured fields should remain available as a source of truth.

## 3. Inventor_QA

### Purpose
The `Inventor_QA` input captures inventor-originated explanatory material collected during discussions, interviews, question-answer sessions, or technical note-taking.

This input may appear in different forms, such as:
- direct question-answer format
- semi-structured inventor interview notes
- informal technical discussion notes
- design clarification notes recorded after a meeting

Therefore, this input should not be treated as only a rigid formal Q&A document.
It is better understood as a source of inventor-provided clarification and interpretation.

This input is especially useful for:
- understanding design intent
- clarifying why certain technical choices were made
- identifying hidden functional reasoning
- identifying geometry or mechanism clues not stated clearly in other documents
- resolving ambiguity in invention disclosure or research report fields

---

### Field

#### `questions_and_answers`
This field stores inventor-provided clarification content.

Even though the field name is `questions_and_answers`, the actual content may take different forms:
- explicit questions followed by answers
- short bullet-point notes from a technical discussion
- explanation fragments recorded during a meeting
- mixed Turkish/English technical notes
- partially interpreted design notes

#### Example content style
A typical entry may include:
- why catadioptric lenses are used
- what a beam splitter does in the invention
- how zoom is achieved
- what the intermediate image plane enables
- whether a component is fixed, rotatable, removable, or adjustable
- what parts of the structure are still flexible and may change for patentability purposes

#### Example
> Why are catadioptric lenses used?  
> - Catadioptric lenses are used to provide extremely long focal lengths while requiring only a relatively short physical length of the lens.  
> - If the optical system becomes too long, packaging problems occur.  
>
> Notes from the inventor discussion:  
> - The inventor states that the true intermediate image plane is not the one initially assumed from the patent figure, but the one on the right side in the actual design interpretation.  
> - If the G22 group on the right side is made mechanically removable, a suitable lens group can be attached according to the aircraft mission need, allowing wavelength-specific imaging.  
> - Focusing means sharpening the image.  
> - The movable lens group provides the zoom function.  
> - Beam splitters determine how wavelength paths are separated or directed.  
> - Because of the intermediate image plane formed through the shared mirror group / common input, wavelength separation becomes easier. A beam splitter cube or filter placed behind the intermediate image plane could allow visible, short-wave, MWIR, or LWIR separation.  
> - By changing the optical system behind the intermediate image plane, the zoom movement may also be increased.  
> - The system most closely resembles a Schmidt-Cassegrain-type structure, although rear-lens variants may be harder to find, so the inventor recommends researching under the broader catadioptric category.  
> - The current system includes two mirrors; the intermediate image plane component may ultimately be realized as a mirror or filter depending on patentability benefit, while the rest are lenses.  
> - The exact motion mechanism is not yet fixed and may still change.

---

### Why it matters
This input is especially valuable because it often contains information that is not expressed clearly in the more formal project documents.

It may reveal:
- why a configuration was chosen
- how an element actually functions
- what part of the geometry is important
- what is fixed versus still flexible
- how the inventor personally interprets the structure and mechanism

This makes it highly useful for downstream modules such as:
- function candidate extraction
- geometry candidate extraction
- ambiguity resolution
- final definition generation

---

### Observations about Inventor_QA
Compared to the invention disclosure and research report:

- this input is often less formal
- it may be more fragmented
- it may contain mixed confidence statements
- it may include tentative ideas, not only finalized facts

Because of this, downstream modules should use it carefully:
- it is highly valuable for interpretation
- but it may require filtering or ranking
- it should not always be treated as equally strong evidence as a structured finalized report

---

## Input design rule for Inventor_QA
This field should be stored as inventor-provided clarification material without forcing it into an overly rigid structure.

Later modules may:
- summarize it
- extract function hints from it
- extract geometry/mechanism hints from it
- identify uncertainty or flexibility from it

But the raw content should remain available as a source of truth because it often contains nuanced invention reasoning not present elsewhere.
