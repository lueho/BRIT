# Proposal: Agentic Monitoring of Separate Biowaste Collection in Europe

- **Status**: Proposed
- **Date**: 2026-03-06

---

## Context

BRIT is evolving from a data management application into a potential semantic reference for waste collection systems across Europe. A practical high-value use case is the continuous monitoring of separate biowaste collection at municipal, regional, and national levels.

Today, the relevant information is fragmented across many sources:

- national legal texts
- municipal waste calendars
- collector web pages
- annual reports
- PDF schedules and policy documents
- spreadsheets and open-data portals

The information is also multilingual, structurally inconsistent, and often described using overlapping local terminology. For example, separate collection of biowaste may be described using different terms, scopes, and system descriptions in each country.

Recent Soilcom work already moved BRIT toward a URI-first controlled vocabulary and curated crosswalk approach. The next step is to use that semantic layer as the foundation for an agentic monitoring system that can discover, extract, normalize, validate, review, and publish comparable facts about biowaste collection across Europe.

This proposal describes how such a system could work and what role BRIT should play.

## Decision

BRIT should become the authoritative semantic and governance layer for a Europe-wide agentic monitoring workflow focused initially on separate biowaste collection.

The proposed system separates responsibilities as follows:

1. **Agentic framework**
   - discovers source documents and datasets
   - extracts candidate facts from unstructured and semi-structured sources
   - proposes mappings from local terms to canonical BRIT concepts
   - detects changes over time and prioritizes uncertain cases for review

2. **BRIT**
   - publishes canonical concepts and stable identifiers for waste collection meaning
   - validates whether proposed mappings and facts use the correct concepts
   - stores curated crosswalks, approved facts, provenance, and review history
   - exposes authoritative machine-readable data for downstream systems

3. **Human review**
   - resolves ambiguous mappings and policy interpretations
   - approves new concepts, aliases, and crosswalk entries
   - arbitrates boundary cases where concepts partially overlap

This proposal recommends that BRIT represent concept identity with canonical URIs, publish scheme-aware controlled vocabularies, and enforce semantic integrity with preflight validation and SHACL-compatible shapes or equivalent rules.

## Why This Matters

A purely relational database with foreign keys is sufficient for internal referential integrity, but it is not sufficient for:

- multilingual concept harmonization
- stable identifiers across environments and exports
- consistent cross-country comparison
- explicit synonym and overlap governance
- reusable mappings outside BRIT
- automated validation of external crosswalk files and extracted facts

In an era of stronger LLMs, this semantic layer becomes more valuable rather than less. LLMs can accelerate discovery and mapping, but they still need a governed reference layer that defines meaning, validates correctness, and preserves institutional memory.

## Proposed Architecture

### 1. Source Discovery Layer

Agents identify relevant sources for each country and administrative level, such as:

- environment ministry portals
- municipal and regional waste service pages
- waste calendars
- legal and regulatory documents
- annual waste management reports
- structured data portals

Each discovered source should be stored with metadata such as:

- source URL
- source type
- country
- catchment or administrative unit
- time coverage
- document language
- retrieval date
- confidence or relevance score

### 2. Extraction Layer

Extraction agents parse text, tables, PDFs, spreadsheets, and web pages to generate candidate statements such as:

- whether separate biowaste collection exists
- the collection system used
- accepted material scope
- collection frequency
- population or housing coverage
- participation rules
- implementation dates
- whether the service is seasonal or year-round

Each extracted statement should include provenance:

- source reference
- exact quoted snippet where possible
- page or section reference where possible
- language of source text
- extraction timestamp
- confidence estimate

### 3. Semantic Mapping Layer

Mapping agents propose canonical BRIT concepts for extracted local terms and phrases.

Examples include mapping local terms for:

- biowaste categories
- collection systems
- sorting methods
- accepted materials
- fee systems
- connection or obligation types
- collection frequencies

Mappings should distinguish between:

- exact canonical match
- close but not exact match
- unresolved term requiring review
- candidate new concept or alias

### 4. Validation Layer

All candidate mappings and facts should be validated against BRIT's authoritative vocabulary and semantic rules.

Core validation rules include:

- target concept URI must exist
- target concept URI must belong to the declared concept scheme
- concepts must not be deprecated unless explicitly allowed
- extracted fact fields must reference concepts from the correct domain
- crosswalk rows must be internally consistent
- required provenance fields must be present

This validation can be implemented as strict preflight checks in BRIT and optionally expressed as SHACL shapes for external reuse and interoperability.

### 5. Review and Governance Layer

Only a subset of extracted facts should require human review. The system should route cases for review when:

- semantic confidence is low
- multiple candidate concepts compete
- source wording implies ambiguous scope
- a mapping conflicts with existing country-pack patterns
- an extracted fact implies a policy change
- a new alias or new canonical concept may be needed

BRIT should store:

- proposed mappings
- approved mappings
- rejected mappings
- review comments
- provenance history
- version history for concept changes

### 6. Publication and Analytics Layer

Once validated and approved, BRIT should provide:

- comparable collection facts across countries
- change histories over time
- country and municipality coverage maps
- Europe-wide dashboards on separate biowaste collection
- machine-readable exports for external consumers

## Role of BRIT

BRIT should not primarily act as the crawler or opaque inference engine. Its core role should be to serve as the authoritative semantic, validation, and governance layer.

### BRIT as Canonical Concept Registry

BRIT should publish canonical identifiers and definitions for concepts such as:

- separate biowaste collection
- kitchen waste
- green waste or garden waste where meaning is intentionally distinct
- door-to-door collection
- bring-bank collection
- fixed weekly collection
- seasonal collection
- mandatory participation

Each concept should ideally expose:

- stable URI
- preferred label
- alternative labels
- optional multilingual labels
- scheme membership
- lifecycle status
- definitions and notes where needed

### BRIT as Validation Authority

BRIT should validate whether agent proposals and external crosswalks are semantically correct. This includes verifying that mappings point to the correct concept, the correct scheme, and a currently valid canonical identifier.

### BRIT as Crosswalk and Review Memory

BRIT should preserve institutional memory by storing:

- curated multilingual aliases
- country-pack crosswalks
- known regional variants
- historical mapping decisions
- review outcomes for ambiguous terms

### BRIT as Machine-Readable Semantic API

Following the preferred architecture, BRIT's API should expose authoritative, reviewable domain data and validation outcomes, while higher-order agent orchestration and interpretation can live in an external agent or MCP layer.

In practice, BRIT should expose authoritative endpoints or exports for:

- concept schemes
- concepts and lifecycle states
- vocabulary snapshots
- crosswalk equivalences
- validation results
- approved collection facts with provenance

## Example Operational Workflow

A French municipal source states that biowaste is collected weekly door-to-door and accepts kitchen waste.

1. A discovery agent finds the source.
2. An extraction agent reads the page or PDF and extracts candidate facts.
3. A mapping agent proposes canonical BRIT URIs for the waste category, collection system, frequency, and accepted materials.
4. BRIT validates whether each proposed URI exists and belongs to the correct concept scheme.
5. If confidence is high and no conflicts exist, the fact enters BRIT as an approved or review-ready candidate depending on policy.
6. If a term is ambiguous or uses an unknown local synonym, a human reviewer resolves it and the approved mapping becomes reusable for future sources.
7. Downstream dashboards and APIs immediately benefit from the new harmonized fact.

## Expected Value

### Operational Value

- faster onboarding of new countries and sources
- fewer silent semantic errors in imports
- lower manual harmonization effort over time
- reusable curated country-pack mappings

### Analytical Value

- reliable cross-country comparison of separate biowaste collection
- time-series monitoring of policy and service changes
- stronger evidence base for benchmarking and research
- more trustworthy dashboards and maps

### Strategic Value

- positions BRIT as a reference layer for waste collection meaning
- creates durable identifiers usable beyond the BRIT application database
- enables partner integrations and machine-to-machine interoperability
- provides a governed foundation for LLM-assisted workflows

## Execution tracking

Active implementation follow-up for this proposal is now tracked in GitHub issue #91.
This document remains the proposal and architectural context rather than a live phased implementation checklist.

## Risks and Mitigations

### Risk: Overconfidence in LLM extraction or mapping

Mitigation:

- keep BRIT as the validation authority
- require provenance for every extracted claim
- route low-confidence or novel mappings to review

### Risk: Concept drift and duplicate meanings

Mitigation:

- govern concepts through canonical URIs rather than labels alone
- maintain aliases and lifecycle states
- record review rationale for difficult mappings

### Risk: Excessive complexity too early

Mitigation:

- start with one domain: separate biowaste collection
- prioritize strict validation and curated crosswalk reuse before broader automation
- keep the first agentic workflow review-heavy rather than fully autonomous

### Risk: Weak interoperability if semantics stay implicit

Mitigation:

- publish vocabulary snapshots and stable identifiers
- express validation rules in a reusable form
- preserve scheme membership and provenance in all exports

## Success Criteria

The proposal should be considered successful if BRIT can support the following outcomes for the biowaste monitoring domain:

- canonical concepts are stable and machine-readable
- multilingual source terms can be mapped to approved canonical concepts
- invalid or cross-scheme mappings are automatically rejected before ingestion
- approved facts are comparable across countries and time
- ambiguous cases are reviewable with clear provenance
- downstream consumers can trust BRIT as the authoritative semantic source

## Consequences

### Positive Consequences

- BRIT gains a high-value strategic role beyond CRUD storage
- semantic harmonization becomes reusable rather than ad hoc
- agentic systems can scale data collection without replacing governance
- Europe-wide waste collection monitoring becomes technically feasible

### Trade-Offs

- concept governance work becomes more explicit and ongoing
- more upfront effort is required for vocabulary design and validation
- review processes must be designed carefully to balance scale and quality

### Consequence for System Boundaries

BRIT should own authoritative concepts, validation, provenance-aware approved facts, and review workflows. External agents should own discovery, extraction, suggestion generation, and orchestration. This keeps BRIT authoritative and auditable while allowing flexible automation outside the core application.
