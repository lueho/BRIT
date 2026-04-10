# Bibliography Module

## Overview
The Bibliography module is a component of the Bioresource Inventory Tool (BRIT) that manages bibliographic references. It provides functionality for storing, organizing, and retrieving information about various types of references such as articles, books, datasets, and websites.

## Features
- Management of bibliographic references with detailed metadata
- Author management with proper name formatting
- License tracking for references
- URL validation for online references
- BibTeX formatting support
- Autocomplete functionality for authors and references

## Models

### Author
Represents an author of a bibliographic reference with fields for:
- First, middle, and last names
- Suffix
- Preferred citation format

### Licence
Represents a license under which a reference is published:
- Name
- Reference URL

### Source
Represents a bibliographic reference with fields for:
- Type (article, dataset, book, website, custom)
- Title
- Authors (many-to-many relationship)
- Publisher
- Journal
- Issue
- Year
- Abbreviation
- Abstract
- License
- URL with validation
- DOI
- Last accessed date

### SourceAuthor
A through model for the many-to-many relationship between Source and Author:
- Maintains the position/order of authors for a reference

## Views
The module provides a complete set of views for managing bibliographic data:
- Dashboard view
- CRUD operations for Authors, Licences, and Sources
- Autocomplete functionality
- URL validation tools

## Entity Relationship Diagram

```mermaid
erDiagram
    Author ||--o{ SourceAuthor : "writes"
    Source ||--o{ SourceAuthor : "has"
    SourceAuthor {
        int position
    }
    Source ||--o| Licence : "licensed_under"
    Source {
        string type
        string title
        string publisher
        string journal
        string issue
        int year
        string abbreviation
        text abstract
        string url
        boolean url_valid
        date url_checked
        string doi
        date last_accessed
    }
    Author {
        string first_names
        string middle_names
        string last_names
        string suffix
        string preferred_citation
    }
    Licence {
        string name
        string reference_url
    }
```

## Integration
The Bibliography module integrates with other BRIT modules by providing bibliographic reference information for objects used throughout the application.
