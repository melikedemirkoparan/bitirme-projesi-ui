# PostgreSQL Database Schema Specification

## Purpose
This document defines the initial PostgreSQL database structure for the patent drafting system.

The backend is expected to be implemented with:
- **FastAPI** for the application/API layer
- **Python ORM models** for database mapping
- **PostgreSQL** as the relational database

The product is planned as a **desktop application** with a Python-based backend architecture.

The system should use ORM-based Python models and map them to PostgreSQL tables cleanly.
This allows the application to:
- manage project data through Python model classes
- persist data into PostgreSQL through ORM mappings
- keep relationships explicit and maintainable

---

## Technology direction

### Database
- PostgreSQL

### Backend
- FastAPI

### Application form
- Desktop application

### Data access style
- ORM-based model layer in Python

### Why this approach
Using ORM models provides a clean bridge between:
- Python application logic
- database tables
- relationship handling
- CRUD operations

This is especially useful in this system because the project contains:
- one-to-one project documents
- one-to-many claim and element records
- many-to-many style claim-element linking through a relation table

---

## Core schema overview
The database is centered around the `Patent` table.

All major project data is linked to a patent/project record.

### Main entities
- `Patent`
- `Invention_disclosure`
- `Research_Reports`
- `Inventor_QA`
- `Claim`
- `Element`
- `Claim_Element`

---

## 1. Patent

### Purpose
The `Patent` table is the main project table.
Each created project/workspace corresponds to one patent record.

### Fields
```text
Patent
------
patent_id: PK
patent_name: STRING
patent_owner: STRING
patent_draft: TEXT
created_at: TIMESTAMP
updated_at: TIMESTAMP

Notes
* patent_draft stores the final full patent draft text generated later in the workflow.
* This table is the central parent table for the rest of the schema
* 
2. Invention_disclosure
Purpose
Stores the structured invention disclosure form for a patent.
Fields
Invention_disclosure
--------------------
idf_id: PK
patent_id: FK UNIQUE
prior_art_and_problems: TEXT
closest_prior_patents: TEXT
novel_features: TEXT
created_at: TIMESTAMP
updated_at: TIMESTAMP
Relationship
* Patent has Invention_disclosure
* cardinality: 1 to 1 at the schema level
* practical interpretation: a patent may have 0 or 1 invention disclosure record
Important note
patent_id must be both:
* FK
* UNIQUE
This is what enforces one-to-one behavior.

3. Research_Reports
Purpose
Stores the structured research report linked to a patent.
Fields
Research_Reports
----------------
research_report_id: PK
patent_id: FK UNIQUE
executive_summary: TEXT
search_strategy: TEXT
classification_and_keywords: TEXT
element_patent_analysis: TEXT
created_at: TIMESTAMP
updated_at: TIMESTAMP
Relationship
* Patent has Research_Reports
* cardinality: 1 to 1 at the schema level
* practical interpretation: a patent may have 0 or 1 research report record
Important note
patent_id must be both:
* FK
* UNIQUE
* 
4. Inventor_QA
Purpose
Stores inventor question-answer notes linked to a patent.
Fields
Inventor_QA
-----------
qna_id: PK
patent_id: FK UNIQUE
questions_and_answers: TEXT
created_at: TIMESTAMP
updated_at: TIMESTAMP
Relationship
* Patent has Inventor_QA
* cardinality: 1 to 1 at the schema level
* practical interpretation: a patent may have 0 or 1 inventor QA record
Important note
patent_id must be both:
* FK
* UNIQUE
* 
5. Claim
Purpose
Stores all claims belonging to a patent project.
Fields
Claim
-----
claim_id: PK
patent_id: FK
claim_number: INTEGER
claim_dependency_type: STRING
claim_category: STRING
parent_claim_id: FK NULLABLE
claim_text: TEXT
created_at: TIMESTAMP
updated_at: TIMESTAMP
Relationship
* Patent has many Claim
* cardinality: 1 to N
Meaning of important fields
* claim_dependency_type
    * expected values: independent, dependent
* claim_category
    * expected values: apparatus, method
* parent_claim_id
    * used only when the claim is dependent
    * must reference another claim in the same patent project
Rules
* if claim_dependency_type = independent, then parent_claim_id = NULL
* if claim_dependency_type = dependent, then parent_claim_id must be set
* 
6. Element
Purpose
Stores the unique patent elements belonging to a patent project.
These elements may come from:
* automatic extraction
* manual user entry
Fields
Element
-------
element_id: PK
patent_id: FK
element_name: STRING
reference_number: INTEGER
definition_text: TEXT
created_at: TIMESTAMP
updated_at: TIMESTAMP
Relationship
* Patent has many Element
* cardinality: 1 to N
Notes
* reference_number stores the patent drawing/text reference number assigned to the element.
* definition_text stores the user-written or later AI-assisted definition.

7. Claim_Element
Purpose
Stores the relationship between claims and elements.
This relation table is required because:
* one claim can contain multiple elements
* one element can appear in multiple claims
Fields
Claim_Element
-------------
claim_element_id: PK
claim_id: FK
element_id: FK
created_at: TIMESTAMP
updated_at: TIMESTAMP
Relationship
* Claim has many Claim_Element
* Element has many Claim_Element
Effective cardinality
This creates a many-to-many style connection between:
* Claim
* Element
through the Claim_Element relation table.

Relationship summary
One-to-one style relationships
* Patent → Invention_disclosure
* Patent → Research_Reports
* Patent → Inventor_QA
These are implemented with:
* foreign key on child table
* unique constraint on patent_id
One-to-many relationships
* Patent → Claim
* Patent → Element
* Claim → Claim_Element
* Element → Claim_Element

ORM mapping intention
The system is expected to define Python ORM model classes for each table.
This means:
* each table should correspond to a Python model
* relationships should be represented explicitly in ORM definitions
* foreign keys should be declared in model fields
* one-to-one and one-to-many behavior should be reflected in the ORM layer
Intended benefit
This allows the FastAPI-based desktop application backend to:
* create and query projects cleanly
* access related records through model relationships
* prepare structured data for prompts and drafting modules
* keep database logic readable and maintainable

Example modeling direction
Typical ORM model coverage should include:
* Patent
* InventionDisclosure
* ResearchReport
* InventorQA
* Claim
* Element
* ClaimElement
These model names may be adapted to Python naming conventions while preserving the table logic.

Design rationale
This schema is designed to support the product workflow already defined in the UI specifications.
Why Patent is central
Because every major workflow depends on the active project:
* document ingestion
* claim drafting
* element definition
* full patent draft generation
Why document tables are separate
The invention disclosure, research report, and inventor QA are separate structured sources and should not be mixed into one large table.
Why claims and elements are separate
Claims and elements serve different drafting purposes:
* claims represent legal drafting units
* elements represent technical components/entities
Why Claim_Element exists
An element may appear in multiple claims. Therefore, element identity and claim usage must be stored separately.
```