# Excel Upload and ChromaDB Ingestion Specification

## Purpose
This module is responsible for handling the Excel upload flow triggered from the navbar's **Upload Data** action.

Its purpose is to:
- open an upload modal
- accept a master Excel file uploaded by the user
- validate the expected column structure
- read patent-related rows from the file
- create ChromaDB vector collections from selected English text columns
- attach useful metadata to each stored vector document

This module is part of the ingestion/indexing workflow.

---

## Trigger
The workflow begins when the user clicks:

- `Upload Data`

from the shared navbar.

### Required behavior
Clicking `Upload Data` must open an **upload modal**, not navigate to a separate page.

The upload modal should:
1. allow the user to select an Excel file
2. submit the file to the upload service
3. show upload / processing status
4. later support indexing feedback if needed

---

## Modal behavior
The upload flow must be implemented as a modal-based interaction.

### The modal should support
- file selection
- upload action
- upload status feedback
- error message display
- success state display

### Important note
This is not a dedicated standalone page in V1.
It is a modal opened from the navbar.

---

## Input file expectation
The uploaded Excel file is expected to contain patent-related rows in a structured tabular form.

The file may contain columns such as:
- `element_id`
- `element_name_en`
- `element_name_tr`
- `definition_en`
- `definition_tr`
- `all_elements_context_en`
- `all_elements_context_tr`
- `description_title_tr`
- `description_title_en` (may be added later; may not exist in current files)
- `source_file`
- `location_ref`

The upload service must not assume that all optional columns are always present.

---

## Core ingestion rule
The ingestion logic must create separate ChromaDB collections for selected English text fields.

The target collections are:

1. `definition_en`
2. `description_title_en`
3. `all_elements_context_en`

Each collection should only be created if the corresponding Excel column exists in the uploaded file.

### Important behavior
- If only one of these columns exists, create only that collection
- If two exist, create only those two collections
- If all three exist, create all three collections
- If one is missing, do not attempt to create its collection

This logic must be dynamic and column-aware.

---

## Collection strategy

### 1. Definition collection
If the uploaded Excel contains `definition_en`, create a collection for English patent definitions.

#### Suggested collection name
- `patent_definition_en`

#### Document source
- `definition_en`

#### Primary purpose
This collection supports retrieval over English patent definition texts.

---

### 2. Description title collection
If the uploaded Excel contains `description_title_en`, create a collection for English invention/domain titles.

#### Suggested collection name
- `patent_description_title_en`

#### Document source
- `description_title_en`

#### Primary purpose
This collection supports retrieval over invention titles / domain titles.

---

### 3. All-elements-context collection
If the uploaded Excel contains `all_elements_context_en`, create a collection for English all-elements context strings.

#### Suggested collection name
- `patent_all_elements_context_en`

#### Document source
- `all_elements_context_en`

#### Primary purpose
This collection supports retrieval over broader element-context text.

---

## Embedding model direction
The ingestion workflow should use an embedding model suitable for English text.

A current example implementation uses:
- `all-MiniLM-L6-v2`

through ChromaDB sentence-transformer embedding integration.

### Important architecture rule
Do not hard-bind the whole application to one permanent embedding model.

The ingestion module should be implemented so that:
- the embedding model can be changed later
- the collection-building workflow does not require a full rewrite when the model changes

The first implementation may use:
- `all-MiniLM-L6-v2`

but the code should remain modular and replaceable.

---

## Metadata rule
Each stored ChromaDB document should include useful metadata derived from the Excel row.

Metadata may include, depending on availability:
- `element_id`
- `element_name_en`
- `element_name_tr`
- `definition_tr`
- `description_title_en`
- `description_title_tr`
- `all_elements_context_en`
- `all_elements_context_tr`
- `source_file`
- `location_ref`

### Important rule
Metadata should be relevant to the collection being created.

For example:

#### For `patent_definition_en`
Useful metadata may include:
- `element_id`
- `element_name_en`
- `element_name_tr`
- `definition_tr`
- `description_title_en`
- `description_title_tr`
- `source_file`
- `location_ref`

#### For `patent_description_title_en`
Useful metadata may include:
- `element_id`
- `element_name_en`
- `element_name_tr`
- `description_title_tr`
- `source_file`

#### For `patent_all_elements_context_en`
Useful metadata may include:
- `element_id`
- `element_name_en`
- `element_name_tr`
- `description_title_en`
- `description_title_tr`
- `source_file`

---

## Row filtering rule
The upload service should only insert rows into a collection when the target document text is actually usable.

### Example rule
For a target column such as `definition_en`:
- ignore missing values
- ignore empty strings
- ignore invalid text such as `"nan"`

The same filtering rule should apply to:
- `description_title_en`
- `all_elements_context_en`

Only valid, non-empty English text should be embedded and stored.

---

## Collection creation behavior
The upload service should:

1. load the Excel file into a dataframe
2. inspect whether each target column exists
3. for each existing target column:
   - create or get the corresponding ChromaDB collection
   - iterate through rows
   - collect valid document text
   - create row-based IDs
   - attach metadata
   - batch insert into the collection

### Important note
Collection creation must be independent per target column.

Do not assume that all target collections are always created together.

---

## ID generation rule
Each stored vector document should receive a stable generated ID.

A simple first version may use row-based IDs such as:
- `definition_en_0`
- `description_title_en_0`
- `all_elements_context_en_0`

or a similarly scoped naming convention.

The important point is:
- IDs should be unique within the collection
- IDs should remain clear and traceable

---

## Persistence direction
The vector database should use a persistent ChromaDB client.

### Example direction
- persistent storage path under a local folder such as `./storage`

The exact path may be configurable through settings later.

---

## Error handling expectations
The ingestion service should handle at least:
- missing file
- unreadable Excel file
- completely missing target columns
- empty usable data in a target column
- ChromaDB initialization errors

### Behavior
If one target column is missing, do not fail the whole process automatically.
Instead:
- skip that collection
- continue with other valid target columns

Only fail the whole upload when:
- the file itself is unusable
- or no meaningful ingestion can be performed

---

## V1 scope
For the first version, this module only needs to:
- open from the navbar as a modal
- accept the Excel file
- inspect the expected columns
- create the relevant ChromaDB collections
- store vectorized documents with metadata
- show basic upload/processing feedback in the modal

It does not yet need to:
- perform advanced cleaning
- normalize all multilingual columns
- deduplicate semantically similar rows
- support complex admin tooling
- expose advanced collection management UI

---

## Future extensions
Possible later improvements include:
- configurable embedding model selection
- configurable ChromaDB storage path
- upload progress reporting
- collection statistics reporting
- row validation report
- deduplication logic
- schema validation against expected Excel structure
- support for additional collections and metadata strategies

These are out of scope for the initial version.

---

## Final implementation rule
Implement this upload-and-ingestion module in a modular way.

Do not tightly couple:
- the upload modal UI
- the upload endpoint
- the Excel parsing logic
- the embedding model
- the ChromaDB collection logic

Keep these concerns separable so that:
- embedding models can change later
- collection behavior can evolve
- the ingestion workflow can be extended without rewriting the whole module
