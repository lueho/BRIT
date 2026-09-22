source("R/bootstrap.R")

#######################################
## Catalonia Impropis data preparation
#######################################

# This script prepares the 2024 Catalonia impurity data at municipi level,
# resolves unambiguous circuit–municipi relations, excludes large-producer
# observations, checks explicit collection-model information against the main
# municipi dataset, documents specific manual decisions, iteratively resolves
# additional circuits reduced to one remaining municipi, and joins the final
# values to eligible Biowaste rows of the main Catalonia dataset.


#######################################
## 1. Packages, helpers and output path
#######################################

# Load the packages used for data preparation and the central BRIT helper file.
# The output directory is defined once and reused for all final exports.

library(tidyverse)
source(
  brit_path(
    "R",
    "helpers.R"
  )
)

output_directory <- brit_path(
  "data",
  "processed",
  "Catalonia"
)

dir.create(
  output_directory,
  recursive = TRUE,
  showWarnings = FALSE
)


#######################################
## 2. Local preparation helpers
#######################################

# These local helpers cover operations specific to this data preparation:
# safe weighted means and sums, collapsing metadata, municipality-name
# normalisation, and UTF-8 CSV export with decimal points.

weighted_mean_safe <- function(x, w, digits = 2) {
  valid <- !is.na(x) &
    !is.na(w) &
    w > 0

  if (!any(valid)) {
    return(NA_real_)
  }

  round(
    weighted.mean(
      x[valid],
      w[valid]
    ),
    digits = digits
  )
}


sum_safe <- function(x, digits = 2) {
  if (all(is.na(x))) {
    return(NA_real_)
  }

  round(
    sum(
      x,
      na.rm = TRUE
    ),
    digits = digits
  )
}


collapse_unique_values <- function(
    x,
    separator = "; "
) {
  values <- sort(
    unique(
      na.omit(x)
    )
  )

  if (length(values) == 0) {
    return(NA_character_)
  }

  str_c(
    values,
    collapse = separator
  )
}


create_municipi_key <- function(x) {
  x %>%
    str_squish() %>%
    str_replace_all(
      "[’‘`´]",
      "'"
    ) %>%
    str_to_upper(
      locale = "ca"
    ) %>%
    stringi::stri_trans_general(
      "Latin-ASCII"
    ) %>%
    str_remove(
      ",\\s*(EL|LA|ELS|LES|L'|ES)$"
    ) %>%
    str_remove(
      "^(EL|LA|ELS|LES|ES)\\s+"
    ) %>%
    str_remove(
      "^L'"
    ) %>%
    str_replace_all(
      "[^A-Z0-9]+",
      " "
    ) %>%
    str_squish()
}


normalise_collection_mode <- function(x) {
  x_clean <- x %>%
    coalesce("") %>%
    str_squish() %>%
    str_to_lower() %>%
    str_replace_all("[–—]", "-")

  has_dtd <-
    str_detect(
      x_clean,
      "dtd|d2d|door\\s*-?\\s*to\\s*-?\\s*door"
    )

  has_bring <-
    str_detect(
      x_clean,
      "bring"
    )

  case_when(
    x_clean == "" ~
      "Unspecified",

    str_detect(
      x_clean,
      "no\\s+separate\\s+collection"
    ) ~
      "No separate collection",

    str_detect(
      x_clean,
      "community\\s+compost"
    ) ~
      "Community composting",

    has_dtd & has_bring ~
      "Mixed Door-to-door and Bring point",

    has_dtd ~
      "Door-to-door",

    has_bring ~
      "Bring point",

    TRUE ~
      "Other"
  )
}


write_utf8_bom_csv <- function(data, path) {
  dir.create(
    dirname(path),
    recursive = TRUE,
    showWarnings = FALSE
  )

  con <- file(
    path,
    open = "wb"
  )

  writeBin(
    as.raw(
      c(
        0xEF,
        0xBB,
        0xBF
      )
    ),
    con
  )

  close(con)

  write_delim(
    data,
    file = path,
    delim = ";",
    na = "",
    quote = "needed",
    append = TRUE,
    col_names = TRUE
  )
}


recalculate_review_counts <- function(data) {
  data %>%
    select(
      -any_of(
        c(
          "n_municipis_per_circuit",
          "n_circuits_per_municipi"
        )
      )
    ) %>%
    group_by(Circuit) %>%
    mutate(
      Municipis_updated = str_c(
        sort(
          unique(
            na.omit(Catchment)
          )
        ),
        collapse = "; "
      ),

      n_municipis_per_circuit =
        n_distinct(
          codi,
          na.rm = TRUE
        )
    ) %>%
    ungroup() %>%
    add_count(
      codi,
      name = "n_circuits_per_municipi"
    )
}


resolve_review_iteratively <- function(review_data) {
  remaining <- recalculate_review_counts(
    review_data
  )

  resolved_iterations <- list()
  removed_shared_iterations <- list()
  iteration <- 0L

  repeat {
    eligible_codi <- remaining %>%
      group_by(codi) %>%
      summarise(
        has_exclusive_circuit = any(
          n_municipis_per_circuit == 1
        ),

        .groups = "drop"
      ) %>%
      filter(
        !is.na(codi),
        has_exclusive_circuit
      ) %>%
      pull(codi)

    if (length(eligible_codi) == 0) {
      break
    }

    iteration <- iteration + 1L

    removed_shared_iterations[[iteration]] <-
      remaining %>%
      filter(
        codi %in% eligible_codi,
        n_municipis_per_circuit > 1
      ) %>%
      mutate(
        resolution_iteration =
          iteration,

        Removal_reason = paste(
          "Municipi resolved from one or more circuits",
          "that had been reduced to this municipi only"
        )
      )

    resolved_iterations[[iteration]] <-
      remaining %>%
      filter(
        codi %in% eligible_codi,
        n_municipis_per_circuit == 1
      ) %>%
      group_by(
        codi,
        Catchment
      ) %>%
      summarise(
        resolution_iteration =
          iteration,

        n_source_circuits =
          n_distinct(Circuit),

        Impropis_percentage =
          weighted_mean_safe(
            Impropis_percentage,
            Mass_tonnes
          ),

        Mass_tonnes =
          sum_safe(Mass_tonnes),

        Circuit =
          collapse_unique_values(Circuit),

        Municipi_Impropis =
          collapse_unique_values(
            Municipi_Impropis,
            separator = " | "
          ),

        Municipi_key =
          first(Municipi_key),

        Municipis_original =
          collapse_unique_values(
            Municipis_original,
            separator = " | "
          ),

        Municipis_updated =
          first(Catchment),

        Collection_model =
          collapse_unique_values(
            Collection_model
          ),

        Catalan =
          collapse_unique_values(
            Catalan
          ),

        Comment =
          collapse_unique_values(
            Comment
          ),

        n_municipis_per_circuit_original =
          max(
            n_municipis_per_circuit_original,
            na.rm = TRUE
          ),

        resolved_by_individual_priority =
          any(
            resolved_by_individual_priority,
            na.rm = TRUE
          ),

        .groups = "drop"
      ) %>%
      mutate(
        Relation_type =
          "Resolved_iterative_review",

        Identification_method = case_when(
          n_source_circuits == 1 ~
            paste(
              "Iterative assignment after circuit",
              "reduced to one remaining municipi"
            ),

          TRUE ~
            paste(
              "Iterative weighted aggregation of circuits",
              "reduced to one remaining municipi"
            )
        ),

        Decision_reason = case_when(
          n_source_circuits == 1 ~
            paste(
              "The selected circuit contained only this municipi",
              "after previously resolved municipis were removed"
            ),

          TRUE ~
            paste(
              "All selected circuits contained only this municipi",
              "after previously resolved municipis were removed"
            )
        ),

        Mass_tonnes_scope = case_when(
          n_source_circuits == 1 ~
            "Original circuit total (not municipi-specific)",

          TRUE ~
            paste(
              "Original circuit totals used as weights",
              "(not municipi-specific)"
            )
        ),

        n_municipis_per_circuit = 1L,

        n_circuits_per_municipi =
          n_source_circuits,

        shared_circuit_reduced_to_one = TRUE,
        resolved_by_manual_decision = FALSE,
        resolved_by_iterative_review = TRUE
      )

    remaining <-
      remaining %>%
      filter(
        !(codi %in% eligible_codi)
      ) %>%
      recalculate_review_counts()
  }

  list(
    resolved =
      bind_rows(
        resolved_iterations
      ),

    removed_shared_assignments =
      bind_rows(
        removed_shared_iterations
      ),

    remaining =
      remaining
  )
}


#######################################
## 3. Import the two source datasets
#######################################

# Import the main municipal waste dataset and the separate Impropis dataset.
# Keeping both imports in this script makes the complete workflow reproducible
# without relying on objects left in the R environment.

Catalonia <- read.csv(
  file = brit_path(
    "data",
    "raw",
    "Catalonia",
    "BRIT_Katalonien_2024_SW_V3.csv"
  ),
  na.strings = "#NV",
  header = TRUE,
  sep = ";",
  dec = ".",
  fileEncoding = "Windows-1252"
)


Catalonia_Impropis_Raw <- read.csv(
  file = brit_path(
    "data",
    "raw",
    "Catalonia",
    "BRIT_Katalonien_2024_Impropis.csv"
  ),
  na.strings = "#NV",
  header = TRUE,
  sep = ";",
  dec = ".",
  fileEncoding = "Windows-1252"
)


#######################################
## 4. Clean the raw Impropis data
#######################################

# Convert mass and impurity values to numeric variables and standardise all
# character fields. The cleaned table is the basis for all later circuit-level
# aggregation and municipality assignment.

Catalonia_Impropis <- Catalonia_Impropis_Raw %>%
  mutate(
    Source_row_id = row_number(),

    Mass_tonnes = parse_double(
      str_squish(
        as.character(Mass_tonnes)
      ),
      locale = locale(
        decimal_mark = "."
      ),
      na = c(
        "",
        "#NV",
        "NA"
      )
    ),

    Impropis_percentage = parse_double(
      str_squish(
        as.character(Impropis_percentage)
      ),
      locale = locale(
        decimal_mark = "."
      ),
      na = c(
        "",
        "#NV",
        "NA"
      )
    ),

    across(
      where(is.character),
      ~ na_if(
        str_squish(.x),
        ""
      )
    )
  )


#######################################
## 5. Exclude large-producer routes
#######################################

# The analysis targets household collection. Observations explicitly marked as
# large-producer routes are stored separately for documentation and removed
# before any collection-model selection or weighted aggregation is performed. If this removal leaves only one
# valid circuit assignment for a municipi, the later relation rules can resolve
# that municipi automatically without retaining the large-producer records.

large_producer_label <-
  "large producers, no households"


Catalonia_Impropis_Large_Producers <-
  Catalonia_Impropis %>%
  filter(
    str_to_lower(
      coalesce(
        Comment,
        ""
      )
    ) == large_producer_label
  )


Catalonia_Impropis <- Catalonia_Impropis %>%
  filter(
    str_to_lower(
      coalesce(
        Comment,
        ""
      )
    ) != large_producer_label
  )


#######################################
## 6. Review repeated raw circuit rows
#######################################

# Do not aggregate raw rows yet. The same Circuit can contain measurements with
# different Collection_model values, and these must be evaluated at source-row
# level before any weighted mean is calculated. This table is only an audit of
# circuits represented by more than one household source row.

Catalonia_Impropis_Raw_Circuit_Check <-
  Catalonia_Impropis %>%
  count(
    Circuit,
    name = "n_source_rows"
  ) %>%
  filter(
    n_source_rows > 1
  ) %>%
  arrange(
    desc(n_source_rows),
    Circuit
  )

Catalonia_Impropis_Raw_Circuit_Check


#######################################
## 7. Create the main municipi lookup
#######################################

# Municipality names from the main Catalonia dataset are normalised and linked
# to their codi. The stable codi identifier is used for the collection-model
# comparison and all subsequent circuit–municipi assignment steps.

Catalonia_Municipi_Lookup <-
  Catalonia %>%
  transmute(
    codi = as.character(codi),
    Catchment,

    Municipi_key =
      create_municipi_key(
        Catchment
      )
  ) %>%
  distinct(
    codi,
    Catchment,
    Municipi_key
  )


Catalonia_Municipi_Lookup_Conflicts <-
  Catalonia_Municipi_Lookup %>%
  count(
    Municipi_key,
    name = "n_codes"
  ) %>%
  filter(
    n_codes > 1
  )

Catalonia_Municipi_Lookup_Conflicts


#######################################
## 8. Create the Biowaste collection-system lookup
#######################################

# The municipi-level Collection_system_2024 is extracted from the Biowaste row
# of the main Catalonia dataset. More than one distinct value for the same codi
# would make the later model comparison ambiguous and is therefore checked
# explicitly before the lookup is used.

Catalonia_Collection_System_Lookup <-
  Catalonia %>%
  filter(
    Waste_Category == "Biowaste"
  ) %>%
  transmute(
    codi = as.character(codi),
    Collection_system_2024
  ) %>%
  distinct()


Catalonia_Collection_System_Conflicts <-
  Catalonia_Collection_System_Lookup %>%
  count(
    codi,
    name = "n_collection_systems"
  ) %>%
  filter(
    n_collection_systems > 1
  )

Catalonia_Collection_System_Conflicts


if (nrow(Catalonia_Collection_System_Conflicts) > 0) {
  stop(
    paste(
      "Conflicting Collection_system_2024 values found for at least one codi.",
      "Resolve Catalonia_Collection_System_Conflicts before continuing."
    )
  )
}


#######################################
## 9. Expand household source rows to municipis
#######################################

# Each original household source row is expanded to one row per listed
# municipi before any circuit aggregation takes place. This preserves the
# original Collection_model, Impropis_percentage and Mass_tonnes combination
# and prevents different collection models from being mixed prematurely.

Catalonia_Impropis_Municipi_Expanded <-
  Catalonia_Impropis %>%
  mutate(
    Municipis_original = Municipis
  ) %>%
  separate_rows(
    Municipis,
    sep = "\\s*;\\s*"
  ) %>%
  rename(
    Municipi_Impropis = Municipis
  ) %>%
  mutate(
    Municipi_Impropis =
      str_squish(
        Municipi_Impropis
      ),

    Municipi_key =
      create_municipi_key(
        Municipi_Impropis
      )
  ) %>%
  left_join(
    Catalonia_Municipi_Lookup,
    by = "Municipi_key",
    relationship = "many-to-one"
  ) %>%
  left_join(
    Catalonia_Collection_System_Lookup,
    by = "codi",
    relationship = "many-to-one"
  ) %>%
  mutate(
    Source_collection_mode =
      normalise_collection_mode(
        Collection_model
      ),

    Target_collection_mode =
      normalise_collection_mode(
        Collection_system_2024
      )
  )


#######################################
## 10. Select source rows by collection model
#######################################

# Collection_model is used as a source-row selection criterion, not as a simple
# exact-match filter:
#
# 1) Empty Collection_model values are unrestricted and remain available.
# 2) For a single-system municipi, an exact source-model match is preferred.
# 3) A source row marked as Mixed is retained as a fallback only when no exact
#    Door-to-door or Bring point source row exists for that municipi.
# 4) For a mixed-system municipi, an explicit Mixed source row is preferred;
#    otherwise Door-to-door and Bring point component rows can both be used.
# 5) Incompatible source models are excluded.
# 6) No separate collection and Community composting receive no Impropis value.
#
# The decision is made while the original source rows are still preserved.

Catalonia_Impropis_Model_Selection <-
  Catalonia_Impropis_Municipi_Expanded %>%
  group_by(
    codi,
    Catchment
  ) %>%
  mutate(
    has_exact_collection_model =
      any(
        Source_collection_mode ==
          Target_collection_mode &
          Source_collection_mode !=
          "Unspecified",
        na.rm = TRUE
      ),

    Use_for_assignment = case_when(
      Target_collection_mode %in%
        c(
          "No separate collection",
          "Community composting"
        ) ~
        FALSE,

      Source_collection_mode ==
        "Unspecified" ~
        TRUE,

      Target_collection_mode ==
        "Door-to-door" &
        Source_collection_mode ==
          "Door-to-door" ~
        TRUE,

      Target_collection_mode ==
        "Door-to-door" &
        Source_collection_mode ==
          "Mixed Door-to-door and Bring point" &
        !has_exact_collection_model ~
        TRUE,

      Target_collection_mode ==
        "Bring point" &
        Source_collection_mode ==
          "Bring point" ~
        TRUE,

      Target_collection_mode ==
        "Bring point" &
        Source_collection_mode ==
          "Mixed Door-to-door and Bring point" &
        !has_exact_collection_model ~
        TRUE,

      Target_collection_mode ==
        "Mixed Door-to-door and Bring point" &
        Source_collection_mode ==
          "Mixed Door-to-door and Bring point" ~
        TRUE,

      Target_collection_mode ==
        "Mixed Door-to-door and Bring point" &
        Source_collection_mode %in%
          c(
            "Door-to-door",
            "Bring point"
          ) &
        !has_exact_collection_model ~
        TRUE,

      TRUE ~
        FALSE
    ),

    Collection_model_selection = case_when(
      Target_collection_mode ==
        "No separate collection" ~
        "Excluded: no separate biowaste collection",

      Target_collection_mode ==
        "Community composting" ~
        "Excluded: community composting",

      Source_collection_mode ==
        "Unspecified" ~
        "Retained: Collection_model not specified",

      Source_collection_mode ==
        Target_collection_mode ~
        "Retained: exact collection-model match",

      Target_collection_mode %in%
        c(
          "Door-to-door",
          "Bring point"
        ) &
        Source_collection_mode ==
          "Mixed Door-to-door and Bring point" &
        !has_exact_collection_model ~
        "Retained: mixed source model used as fallback",

      Target_collection_mode %in%
        c(
          "Door-to-door",
          "Bring point"
        ) &
        Source_collection_mode ==
          "Mixed Door-to-door and Bring point" &
        has_exact_collection_model ~
        "Excluded: mixed source model superseded by exact match",

      Target_collection_mode ==
        "Mixed Door-to-door and Bring point" &
        Source_collection_mode %in%
          c(
            "Door-to-door",
            "Bring point"
          ) &
        !has_exact_collection_model ~
        "Retained: component model used for mixed collection system",

      Target_collection_mode ==
        "Mixed Door-to-door and Bring point" &
        Source_collection_mode %in%
          c(
            "Door-to-door",
            "Bring point"
          ) &
        has_exact_collection_model ~
        "Excluded: component model superseded by exact mixed-system match",

      Target_collection_mode ==
        "Unspecified" ~
        "Excluded: Collection_system_2024 unavailable",

      Source_collection_mode ==
        "Other" ~
        "Excluded: unrecognised source Collection_model",

      TRUE ~
        "Excluded: incompatible collection model"
    )
  ) %>%
  ungroup()


#######################################
## 11. Audit collection-model decisions
#######################################

# Keep the complete source-row-level decision table for manual inspection.
# Unlike the previous binary mismatch table, this shows the exact raw model,
# the municipi-level system, whether an exact alternative exists, and why each
# row is retained or excluded.

Catalonia_Impropis_Collection_Model_Check <-
  Catalonia_Impropis_Model_Selection %>%
  select(
    Source_row_id,
    Catchment,
    codi,
    Circuit,
    Collection_model,
    Source_collection_mode,
    Collection_system_2024,
    Target_collection_mode,
    has_exact_collection_model,
    Use_for_assignment,
    Collection_model_selection,
    Impropis_percentage,
    Mass_tonnes,
    Municipis_original,
    Comment
  ) %>%
  arrange(
    Catchment,
    desc(Use_for_assignment),
    Circuit,
    Source_row_id
  )

Catalonia_Impropis_Collection_Model_Check


Catalonia_Impropis_Collection_Model_Excluded <-
  Catalonia_Impropis_Collection_Model_Check %>%
  filter(
    !Use_for_assignment
  )

Catalonia_Impropis_Collection_Model_Excluded


Catalonia_Impropis_Collection_Model_Check_Summary <-
  Catalonia_Impropis_Collection_Model_Check %>%
  count(
    Collection_model_selection,
    Use_for_assignment,
    name = "n_assignments",
    sort = TRUE
  )

Catalonia_Impropis_Collection_Model_Check_Summary


# Municipis for which source data exist but no source row remains after the
# collection-model rules are listed separately. These cases intentionally
# receive no automatic Impropis assignment.

Catalonia_Impropis_Collection_Model_No_Assignment <-
  Catalonia_Impropis_Model_Selection %>%
  group_by(
    codi,
    Catchment,
    Collection_system_2024,
    Target_collection_mode
  ) %>%
  summarise(
    n_source_assignments = n(),

    n_selected_assignments =
      sum(
        Use_for_assignment,
        na.rm = TRUE
      ),

    Source_models_available =
      collapse_unique_values(
        Source_collection_mode
      ),

    Circuits_available =
      collapse_unique_values(
        Circuit
      ),

    .groups = "drop"
  ) %>%
  filter(
    !is.na(codi),
    n_selected_assignments == 0
  ) %>%
  arrange(Catchment)

Catalonia_Impropis_Collection_Model_No_Assignment


#######################################
## 12. Aggregate selected rows to circuit–municipi level
#######################################

# Only source rows accepted by the collection-model rules are now aggregated.
# The weighted mean is therefore calculated separately for each
# Circuit–municipi combination from compatible source rows only. This prevents
# Door-to-door, Bring point and Mixed measurements from being combined before
# the correct municipi-level model has been established.

Catalonia_Impropis_Municipi_Base <-
  Catalonia_Impropis_Model_Selection %>%
  filter(
    Use_for_assignment,
    !is.na(codi)
  ) %>%
  group_by(
    Circuit,
    codi,
    Catchment
  ) %>%
  summarise(
    n_source_rows =
      n_distinct(
        Source_row_id
      ),

    n_plants =
      n_distinct(
        Planta,
        na.rm = TRUE
      ),

    Impropis_percentage =
      weighted_mean_safe(
        Impropis_percentage,
        Mass_tonnes
      ),

    Mass_tonnes =
      sum_safe(
        Mass_tonnes
      ),

    Municipi_Impropis =
      collapse_unique_values(
        Municipi_Impropis,
        separator = " | "
      ),

    Municipi_key =
      first(Municipi_key),

    Municipis_original =
      collapse_unique_values(
        Municipis_original,
        separator = " | "
      ),

    Collection_model =
      collapse_unique_values(
        Collection_model
      ),

    Collection_system_2024 =
      first(
        Collection_system_2024
      ),

    Collection_model_selection =
      collapse_unique_values(
        Collection_model_selection,
        separator = " | "
      ),

    Catalan =
      collapse_unique_values(
        Catalan
      ),

    Comment =
      collapse_unique_values(
        Comment
      ),

    .groups = "drop"
  ) %>%
  add_count(
    Circuit,
    name = "n_municipis_per_circuit"
  ) %>%
  add_count(
    codi,
    name = "n_circuits_per_municipi"
  )


Catalonia_Impropis_Merged_Check <-
  Catalonia_Impropis_Municipi_Base %>%
  filter(
    n_source_rows > 1
  ) %>%
  arrange(
    desc(n_source_rows),
    Catchment,
    Circuit
  )

Catalonia_Impropis_Merged_Check


#######################################
## 13. Check unmatched municipis
#######################################

# Any expanded household row without codi could not be matched to the main
# municipality lookup. These names are reported independently from the
# collection-model selection because they cannot enter the assignment logic.

Catalonia_Impropis_Unmatched <-
  Catalonia_Impropis_Municipi_Expanded %>%
  filter(
    is.na(codi)
  ) %>%
  distinct(
    Municipi_Impropis,
    Municipi_key
  ) %>%
  arrange(
    Municipi_Impropis
  )

Catalonia_Impropis_Unmatched


#######################################
## 14. Identify individual/shared overlaps
#######################################

# A municipality may occur in both an exclusive circuit and a shared circuit.
# In these cases, the exclusive municipi-specific circuit is preferred and the
# municipality is removed from its shared-circuit assignment.

Catalonia_Impropis_Individual_Priority <-
  Catalonia_Impropis_Municipi_Base %>%
  group_by(
    codi,
    Catchment
  ) %>%
  summarise(
    has_individual_circuit = any(
      n_municipis_per_circuit == 1
    ),

    has_shared_circuit = any(
      n_municipis_per_circuit > 1
    ),

    .groups = "drop"
  ) %>%
  filter(
    has_individual_circuit,
    has_shared_circuit
  )


Catalonia_Impropis_Removed_Shared_Assignments <-
  Catalonia_Impropis_Municipi_Base %>%
  semi_join(
    Catalonia_Impropis_Individual_Priority,
    by = c(
      "codi",
      "Catchment"
    )
  ) %>%
  filter(
    n_municipis_per_circuit > 1
  ) %>%
  mutate(
    Removal_reason =
      "Municipi-specific circuit available"
  )


#######################################
## 15. Apply the individual-circuit priority
#######################################

# Remove the identified shared assignments and recalculate the number and list
# of municipalities remaining in each circuit. A flag records whether a formerly
# shared circuit becomes assignable to only one remaining municipality.

Catalonia_Impropis_Municipi_Priority <-
  Catalonia_Impropis_Municipi_Base %>%
  mutate(
    n_municipis_per_circuit_original =
      n_municipis_per_circuit,

    resolved_by_individual_priority =
      codi %in%
        Catalonia_Impropis_Individual_Priority$codi &
      n_municipis_per_circuit == 1
  ) %>%
  anti_join(
    Catalonia_Impropis_Removed_Shared_Assignments %>%
      distinct(
        Circuit,
        codi
      ),
    by = c(
      "Circuit",
      "codi"
    )
  ) %>%
  select(
    -n_municipis_per_circuit,
    -n_circuits_per_municipi
  ) %>%
  group_by(Circuit) %>%
  mutate(
    Municipis_updated = str_c(
      sort(
        unique(Catchment)
      ),
      collapse = "; "
    ),

    n_municipis_per_circuit =
      n_distinct(codi),

    shared_circuit_reduced_to_one =
      n_municipis_per_circuit == 1 &
      first(
        n_municipis_per_circuit_original
      ) > 1
  ) %>%
  ungroup() %>%
  add_count(
    codi,
    name = "n_circuits_per_municipi"
  )


#######################################
## 16. Reclassify circuit–municipi relations
#######################################

# Relations are classified again after the priority removals. Direct, exclusive
# multi-circuit, and single shared-circuit cases can be used automatically;
# overlapping combinations remain in the manual-review group.

Catalonia_Impropis_Municipi_Priority <-
  Catalonia_Impropis_Municipi_Priority %>%
  group_by(codi) %>%
  mutate(
    has_current_shared_circuit = any(
      n_municipis_per_circuit > 1
    ),

    has_original_shared_circuit = any(
      n_municipis_per_circuit_original > 1
    ),

    Relation_type = case_when(
      n_circuits_per_municipi == 1 &
        n_municipis_per_circuit == 1 ~
        "Direct",

      n_circuits_per_municipi > 1 &
        !has_current_shared_circuit &
        !has_original_shared_circuit ~
        "Aggregate_single_municipi_circuits",

      n_circuits_per_municipi == 1 &
        n_municipis_per_circuit > 1 ~
        "Shared_circuit_single_assignment",

      TRUE ~
        "Manual_review_overlap"
    ),

    Identification_method = case_when(
      resolved_by_individual_priority ~
        "Municipi-specific circuit preferred over shared circuit",

      shared_circuit_reduced_to_one ~
        "Shared circuit reduced to one remaining municipi",

      Relation_type == "Direct" ~
        "Direct circuit–municipi assignment",

      Relation_type ==
        "Aggregate_single_municipi_circuits" ~
        "Weighted aggregation of municipi-specific circuits",

      Relation_type ==
        "Shared_circuit_single_assignment" ~
        "Shared circuit value assigned to all listed municipis",

      TRUE ~
        "Manual review required"
    )
  ) %>%
  ungroup() %>%
  arrange(
    Relation_type,
    Catchment,
    Circuit
  )


#######################################
## 17. Summarise the updated relations
#######################################

# This overview reports the number of remaining circuit–municipi assignments
# in each relation class after the automatic priority rule has been applied.

Catalonia_Impropis_Relation_Summary <-
  Catalonia_Impropis_Municipi_Priority %>%
  distinct(
    Circuit,
    codi,
    Relation_type
  ) %>%
  count(
    Relation_type,
    name = "n_assignments"
  )

Catalonia_Impropis_Relation_Summary


#######################################
## 18. Aggregate exclusive municipi circuits
#######################################

# If one municipality has several circuits and all are municipi-specific,
# their impurity values are combined as a mass-weighted mean. The circuit
# masses can therefore also be summed at municipality level.

Catalonia_Impropis_Aggregated <-
  Catalonia_Impropis_Municipi_Priority %>%
  filter(
    Relation_type ==
      "Aggregate_single_municipi_circuits"
  ) %>%
  group_by(
    codi,
    Catchment
  ) %>%
  summarise(
    n_source_circuits =
      n_distinct(Circuit),

    Circuit =
      collapse_unique_values(Circuit),

    Municipi_Impropis =
      collapse_unique_values(
        Municipi_Impropis,
        separator = " | "
      ),

    Municipi_key =
      first(Municipi_key),

    Municipis_original =
      collapse_unique_values(
        Municipis_original,
        separator = " | "
      ),

    Municipis_updated =
      collapse_unique_values(
        Municipis_updated,
        separator = " | "
      ),

    Impropis_percentage =
      weighted_mean_safe(
        Impropis_percentage,
        Mass_tonnes
      ),

    Mass_tonnes =
      sum_safe(Mass_tonnes),

    Collection_model =
      collapse_unique_values(
        Collection_model
      ),

    Catalan =
      collapse_unique_values(
        Catalan
      ),

    Comment =
      collapse_unique_values(
        Comment
      ),

    resolved_by_individual_priority =
      any(
        resolved_by_individual_priority
      ),

    shared_circuit_reduced_to_one =
      any(
        shared_circuit_reduced_to_one
      ),

    n_municipis_per_circuit_original =
      max(
        n_municipis_per_circuit_original,
        na.rm = TRUE
      ),

    .groups = "drop"
  ) %>%
  mutate(
    Relation_type =
      "Aggregate_single_municipi_circuits",

    Identification_method = case_when(
      resolved_by_individual_priority ~
        paste(
          "Weighted aggregation of municipi-specific circuits",
          "after removal from shared circuits"
        ),

      TRUE ~
        "Weighted aggregation of municipi-specific circuits"
    ),

    n_municipis_per_circuit = 1L,

    n_circuits_per_municipi =
      n_source_circuits,

    Mass_tonnes_scope =
      "Municipi-specific"
  )


#######################################
## 19. Retain direct and shared assignments
#######################################

# Direct cases are already municipality-specific. A municipality appearing in
# one shared circuit also receives that circuit-level impurity value, but the
# associated mass is explicitly marked as not municipality-specific.

Catalonia_Impropis_Direct_Shared <-
  Catalonia_Impropis_Municipi_Priority %>%
  filter(
    Relation_type %in%
      c(
        "Direct",
        "Shared_circuit_single_assignment"
      )
  ) %>%
  mutate(
    n_source_circuits = 1L,

    Mass_tonnes_scope = case_when(
      n_municipis_per_circuit_original > 1 ~
        "Original circuit total (not municipi-specific)",

      TRUE ~
        "Municipi-specific"
    )
  )


#######################################
## 20. Build the automatically resolved table
#######################################

# Combine aggregated, direct, and usable shared-circuit cases into one table
# containing one final impurity value per automatically resolved municipi.
# Manual and iterative decision fields are added now to retain one schema.

Catalonia_Impropis_Municipi_Simple <-
  bind_rows(
    Catalonia_Impropis_Aggregated,
    Catalonia_Impropis_Direct_Shared
  ) %>%
  mutate(
    Decision_reason = NA_character_,
    resolution_iteration = NA_integer_,
    resolved_by_manual_decision = FALSE,
    resolved_by_iterative_review = FALSE
  ) %>%
  select(
    Catchment,
    codi,
    Relation_type,
    Identification_method,
    Decision_reason,
    resolution_iteration,
    Circuit,
    Municipi_Impropis,
    Municipi_key,
    Municipis_original,
    Municipis_updated,
    Mass_tonnes,
    Mass_tonnes_scope,
    Impropis_percentage,
    Collection_model,
    Catalan,
    Comment,
    n_source_circuits,
    n_municipis_per_circuit_original,
    n_municipis_per_circuit,
    n_circuits_per_municipi,
    resolved_by_individual_priority,
    shared_circuit_reduced_to_one,
    resolved_by_manual_decision,
    resolved_by_iterative_review
  ) %>%
  arrange(
    Catchment,
    Circuit
  )


#######################################
## 21. Build the preliminary review table
#######################################

# All overlapping relations that cannot yet be resolved automatically are
# retained for review. Orís and Fogars de la Selva are resolved manually first;
# the remaining table is then passed to the iterative resolution procedure.

Catalonia_Impropis_Manual_Review <-
  Catalonia_Impropis_Municipi_Priority %>%
  filter(
    Relation_type ==
      "Manual_review_overlap"
  ) %>%
  mutate(
    Mass_tonnes_scope = case_when(
      n_municipis_per_circuit_original > 1 ~
        "Original circuit total (not municipi-specific)",

      TRUE ~
        "Municipi-specific"
    ),

    Decision_reason = NA_character_,
    resolution_iteration = NA_integer_,
    resolved_by_manual_decision = FALSE,
    resolved_by_iterative_review = FALSE
  ) %>%
  select(
    Catchment,
    codi,
    Relation_type,
    Identification_method,
    Decision_reason,
    resolution_iteration,
    Circuit,
    Municipi_Impropis,
    Municipi_key,
    Municipis_original,
    Municipis_updated,
    Collection_model,
    Mass_tonnes,
    Mass_tonnes_scope,
    Impropis_percentage,
    Catalan,
    Comment,
    n_municipis_per_circuit_original,
    n_municipis_per_circuit,
    n_circuits_per_municipi,
    resolved_by_individual_priority,
    shared_circuit_reduced_to_one,
    resolved_by_manual_decision,
    resolved_by_iterative_review
  ) %>%
  arrange(
    Catchment,
    Circuit
  )


#######################################
## 22. Store automatically priority-resolved cases
#######################################

# This audit table isolates municipis resolved specifically through the
# individual-circuit priority or because a shared circuit was reduced to one
# remaining municipi before the manual and iterative review stages.

Catalonia_Impropis_Resolved_By_Priority <-
  Catalonia_Impropis_Municipi_Simple %>%
  filter(
    resolved_by_individual_priority |
      shared_circuit_reduced_to_one
  ) %>%
  arrange(
    Identification_method,
    Catchment,
    Circuit
  )


#######################################
## 23. Manually resolve Fogars de la Selva
#######################################

# Fogars de la Selva is represented by Selva-04 and Selva-09. Both selected
# circuits are combined using their mass values as weights. The masses remain
# documented as original circuit totals rather than municipi-specific mass.

Catalonia_Impropis_Resolved_Fogars <-
  Catalonia_Impropis_Municipi_Priority %>%
  filter(
    Catchment == "Fogars de la Selva",
    Circuit %in% c(
      "Selva-04",
      "Selva-09"
    )
  ) %>%
  group_by(
    codi,
    Catchment
  ) %>%
  summarise(
    n_source_circuits =
      n_distinct(Circuit),

    Impropis_percentage =
      weighted_mean_safe(
        Impropis_percentage,
        Mass_tonnes
      ),

    Mass_tonnes =
      sum_safe(Mass_tonnes),

    Circuit =
      collapse_unique_values(Circuit),

    Municipi_Impropis =
      first(Municipi_Impropis),

    Municipi_key =
      first(Municipi_key),

    Municipis_original =
      collapse_unique_values(
        Municipis_original,
        separator = " | "
      ),

    Municipis_updated =
      first(Catchment),

    Collection_model =
      collapse_unique_values(
        Collection_model
      ),

    Catalan =
      collapse_unique_values(
        Catalan
      ),

    Comment =
      collapse_unique_values(
        Comment
      ),

    n_municipis_per_circuit_original =
      max(
        n_municipis_per_circuit_original,
        na.rm = TRUE
      ),

    resolved_by_individual_priority =
      any(
        resolved_by_individual_priority
      ),

    shared_circuit_reduced_to_one =
      any(
        shared_circuit_reduced_to_one
      ),

    .groups = "drop"
  ) %>%
  mutate(
    Relation_type =
      "Resolved_manual_review",

    Identification_method =
      "Manual weighted aggregation of selected circuits",

    Decision_reason = paste(
      "Selva-04 and Selva-09 were assigned to",
      "Fogars de la Selva after previous removals"
    ),

    resolution_iteration = NA_integer_,

    Mass_tonnes_scope = paste(
      "Original circuit totals used as weights",
      "(not municipi-specific)"
    ),

    n_municipis_per_circuit = 1L,

    n_circuits_per_municipi =
      n_source_circuits,

    resolved_by_manual_decision = TRUE,
    resolved_by_iterative_review = FALSE
  )


#######################################
## 24. Manually resolve Orís
#######################################

# Orís occurs in Osona-01 and Osona-10. Based on the manual source review,
# Osona-10 is selected because it represents several measurements, whereas
# Osona-01 is based on only one measurement.

Catalonia_Impropis_Resolved_Oris <-
  Catalonia_Impropis_Municipi_Priority %>%
  filter(
    Catchment == "Orís",
    Circuit == "Osona-10"
  ) %>%
  transmute(
    Catchment,
    codi,

    Relation_type =
      "Resolved_manual_review",

    Identification_method =
      "Manual selection of preferred circuit",

    Decision_reason = paste(
      "Osona-10 selected because it represents",
      "multiple measurements; Osona-01 was excluded",
      "because it was measured only once"
    ),

    resolution_iteration = NA_integer_,
    Circuit,
    Municipi_Impropis,
    Municipi_key,
    Municipis_original,
    Municipis_updated = Catchment,
    Mass_tonnes,

    Mass_tonnes_scope =
      "Original circuit total (not municipi-specific)",

    Impropis_percentage,
    Collection_model,
    Catalan,
    Comment,

    n_source_circuits = 1L,
    n_municipis_per_circuit_original,
    n_municipis_per_circuit = 1L,
    n_circuits_per_municipi = 1L,

    resolved_by_individual_priority = FALSE,
    shared_circuit_reduced_to_one = FALSE,
    resolved_by_manual_decision = TRUE,
    resolved_by_iterative_review = FALSE
  )


#######################################
## 25. Manually aggregate Torrefarrera and Rosselló
#######################################

# Both remaining household circuit values are retained for Torrefarrera and
# Rosselló. Their 2024 impurity value is calculated as a mass-weighted mean
# using the original circuit totals as weights.

Catalonia_Impropis_Resolved_Torrefarrera_Rossello <-
  Catalonia_Impropis_Manual_Review %>%
  filter(
    Catchment %in%
      c(
        "Torrefarrera",
        "Rosselló"
      )
  ) %>%
  group_by(
    codi,
    Catchment
  ) %>%
  summarise(
    n_source_circuits =
      n_distinct(Circuit),

    Impropis_percentage =
      weighted_mean_safe(
        Impropis_percentage,
        Mass_tonnes
      ),

    Mass_tonnes =
      sum_safe(Mass_tonnes),

    Circuit =
      collapse_unique_values(Circuit),

    Municipi_Impropis =
      collapse_unique_values(
        Municipi_Impropis,
        separator = " | "
      ),

    Municipi_key =
      first(Municipi_key),

    Municipis_original =
      collapse_unique_values(
        Municipis_original,
        separator = " | "
      ),

    Municipis_updated =
      first(Catchment),

    Collection_model =
      collapse_unique_values(
        Collection_model
      ),

    Catalan =
      collapse_unique_values(
        Catalan
      ),

    Comment =
      collapse_unique_values(
        Comment
      ),

    n_municipis_per_circuit_original =
      max(
        n_municipis_per_circuit_original,
        na.rm = TRUE
      ),

    .groups = "drop"
  ) %>%
  mutate(
    Relation_type =
      "Resolved_manual_review",

    Identification_method =
      "Manual weighted aggregation of overlapping household circuits",

    Decision_reason =
      "All remaining household circuit values were retained and combined using circuit mass as weighting",

    resolution_iteration = NA_integer_,

    Mass_tonnes_scope =
      "Original circuit totals used as weights (not municipi-specific)",

    n_municipis_per_circuit = 1L,
    n_circuits_per_municipi = n_source_circuits,

    resolved_by_individual_priority = FALSE,
    shared_circuit_reduced_to_one = FALSE,
    resolved_by_manual_decision = TRUE,
    resolved_by_iterative_review = FALSE
  )


#######################################
## 26. Integrate the documented manual decisions
#######################################

# Combine the remaining explicitly documented manual decisions. el Bruc and
# la Pobla de Claramunt are no longer hard-coded here because large-producer
# source rows are excluded in Step 5 and the remaining household assignments
# are handled by the general rules above.

Catalonia_Impropis_Resolved_Manual <-
  bind_rows(
    Catalonia_Impropis_Resolved_Fogars,
    Catalonia_Impropis_Resolved_Oris,
    Catalonia_Impropis_Resolved_Torrefarrera_Rossello
  ) %>%
  select(
    Catchment,
    codi,
    Relation_type,
    Identification_method,
    Decision_reason,
    resolution_iteration,
    Circuit,
    Municipi_Impropis,
    Municipi_key,
    Municipis_original,
    Municipis_updated,
    Mass_tonnes,
    Mass_tonnes_scope,
    Impropis_percentage,
    Collection_model,
    Catalan,
    Comment,
    n_source_circuits,
    n_municipis_per_circuit_original,
    n_municipis_per_circuit,
    n_circuits_per_municipi,
    resolved_by_individual_priority,
    shared_circuit_reduced_to_one,
    resolved_by_manual_decision,
    resolved_by_iterative_review
  ) %>%
  arrange(Catchment)


resolved_manual_codi <-
  Catalonia_Impropis_Resolved_Manual$codi


Catalonia_Impropis_Municipi_Simple <-
  Catalonia_Impropis_Municipi_Simple %>%
  filter(
    !(codi %in% resolved_manual_codi)
  ) %>%
  bind_rows(
    Catalonia_Impropis_Resolved_Manual
  ) %>%
  arrange(
    Catchment,
    Circuit
  )


#######################################
## 27. Update the review after manual decisions
#######################################

# Remove all specifically resolved municipis from the preliminary review table
# and recalculate the remaining municipi lists and counts. These removals may
# create further exclusive circuits, which are handled iteratively next.

Catalonia_Impropis_Manual_Review <-
  Catalonia_Impropis_Manual_Review %>%
  filter(
    !(codi %in% resolved_manual_codi)
  ) %>%
  recalculate_review_counts() %>%
  arrange(
    Catchment,
    Circuit
  )


#######################################
## 28. Resolve newly exclusive circuits iteratively
#######################################

# A circuit may become exclusive after already resolved municipis are removed.
# In each iteration, every municipi with at least one such exclusive circuit is
# resolved from its exclusive circuit(s), removed from its other shared circuits,
# and all remaining circuit memberships are recalculated before the next round.

Catalonia_Impropis_Iterative_Result <-
  resolve_review_iteratively(
    Catalonia_Impropis_Manual_Review
  )


Catalonia_Impropis_Resolved_Iterative <-
  Catalonia_Impropis_Iterative_Result$resolved %>%
  select(
    Catchment,
    codi,
    Relation_type,
    Identification_method,
    Decision_reason,
    resolution_iteration,
    Circuit,
    Municipi_Impropis,
    Municipi_key,
    Municipis_original,
    Municipis_updated,
    Mass_tonnes,
    Mass_tonnes_scope,
    Impropis_percentage,
    Collection_model,
    Catalan,
    Comment,
    n_source_circuits,
    n_municipis_per_circuit_original,
    n_municipis_per_circuit,
    n_circuits_per_municipi,
    resolved_by_individual_priority,
    shared_circuit_reduced_to_one,
    resolved_by_manual_decision,
    resolved_by_iterative_review
  ) %>%
  arrange(
    resolution_iteration,
    Catchment
  )


Catalonia_Impropis_Iterative_Removed_Shared_Assignments <-
  Catalonia_Impropis_Iterative_Result$removed_shared_assignments %>%
  arrange(
    resolution_iteration,
    Catchment,
    Circuit
  )


Catalonia_Impropis_Manual_Review <-
  Catalonia_Impropis_Iterative_Result$remaining %>%
  arrange(
    Catchment,
    Circuit
  )


Catalonia_Impropis_Iterative_Summary <-
  Catalonia_Impropis_Resolved_Iterative %>%
  count(
    resolution_iteration,
    name = "n_resolved_municipis"
  )

Catalonia_Impropis_Iterative_Summary


#######################################
## 29. Integrate the iterative resolutions
#######################################

# Add the iteratively resolved municipis to the main resolved table. The final
# review table now contains only overlaps for which every remaining circuit
# still contains at least two unresolved municipis.

resolved_iterative_codi <-
  Catalonia_Impropis_Resolved_Iterative$codi


Catalonia_Impropis_Municipi_Simple <-
  Catalonia_Impropis_Municipi_Simple %>%
  filter(
    !(codi %in% resolved_iterative_codi)
  ) %>%
  bind_rows(
    Catalonia_Impropis_Resolved_Iterative
  ) %>%
  arrange(
    Catchment,
    Circuit
  )


#######################################
## 29A. Classify remaining municipis
#######################################

# Apply the final assignment rules only to municipis that still remain in the
# manual-review table after all previously established assignment steps:
#
# 1 valid 2024 value:
#   -> direct assignment
#
# >=2 valid 2024 values with a range below 2 percentage points:
#   -> mass-weighted approximation
#
# >=2 valid 2024 values with a range of 2 percentage points or more:
#   -> retain for comparison in Step 29E before applying the same
#      mass-weighted approximation in Step 29F.

manual_review_difference_threshold_pp <- 2


Catalonia_Impropis_Remaining_Variation <-
  Catalonia_Impropis_Manual_Review %>%
  group_by(
    codi,
    Catchment
  ) %>%
  summarise(
    n_candidate_circuits =
      n_distinct(Circuit),

    n_valid_values =
      sum(
        !is.na(
          Impropis_percentage
        )
      ),

    min_impropis_2024 = if (
      all(
        is.na(
          Impropis_percentage
        )
      )
    ) {
      NA_real_
    } else {
      min(
        Impropis_percentage,
        na.rm = TRUE
      )
    },

    max_impropis_2024 = if (
      all(
        is.na(
          Impropis_percentage
        )
      )
    ) {
      NA_real_
    } else {
      max(
        Impropis_percentage,
        na.rm = TRUE
      )
    },

    .groups = "drop"
  ) %>%
  mutate(
    impurity_range_2024_pp =
      round(
        max_impropis_2024 -
          min_impropis_2024,
        2
      ),

    Resolution_group = case_when(
      n_valid_values == 1 ~
        "Direct assignment",

      n_valid_values >= 2 &
        impurity_range_2024_pp <
          manual_review_difference_threshold_pp ~
        "Weighted approximation (<2 pp range)",

      n_valid_values >= 2 &
        impurity_range_2024_pp >=
          manual_review_difference_threshold_pp ~
        "Weighted approximation after review (>=2 pp range)",

      TRUE ~
        "No valid value"
    )
  ) %>%
  arrange(
    Resolution_group,
    Catchment
  )

Catalonia_Impropis_Remaining_Variation


#######################################
## 29B. Resolve single remaining values
#######################################

# A municipi is assigned directly only when exactly one valid 2024 impurity
# value remains. If two or more valid values remain, none of them is selected
# directly; they are handled through weighted aggregation instead.

Catalonia_Impropis_Direct_Remaining_Codi <-
  Catalonia_Impropis_Remaining_Variation %>%
  filter(
    Resolution_group ==
      "Direct assignment"
  ) %>%
  pull(codi)


Catalonia_Impropis_Resolved_Direct_Remaining <-
  Catalonia_Impropis_Manual_Review %>%
  filter(
    codi %in%
      Catalonia_Impropis_Direct_Remaining_Codi,
    !is.na(
      Impropis_percentage
    )
  ) %>%
  mutate(
    Relation_type =
      "Resolved_single_remaining_value",

    Identification_method =
      "Direct assignment of single remaining impurity value",

    Decision_reason =
      "Only one valid 2024 impurity value remained for the municipi",

    resolution_iteration =
      NA_integer_,

    n_source_circuits =
      1L,

    Mass_tonnes_scope = case_when(
      n_municipis_per_circuit_original > 1 ~
        "Original circuit total (not municipi-specific)",

      TRUE ~
        "Municipi-specific"
    ),

    resolved_by_manual_decision =
      FALSE,

    resolved_by_iterative_review =
      FALSE
  ) %>%
  select(
    Catchment,
    codi,
    Relation_type,
    Identification_method,
    Decision_reason,
    resolution_iteration,
    Circuit,
    Municipi_Impropis,
    Municipi_key,
    Municipis_original,
    Municipis_updated,
    Mass_tonnes,
    Mass_tonnes_scope,
    Impropis_percentage,
    Collection_model,
    Catalan,
    Comment,
    n_source_circuits,
    n_municipis_per_circuit_original,
    n_municipis_per_circuit,
    n_circuits_per_municipi,
    resolved_by_individual_priority,
    shared_circuit_reduced_to_one,
    resolved_by_manual_decision,
    resolved_by_iterative_review
  ) %>%
  arrange(Catchment)


#######################################
## 29C. Resolve low-variation overlaps
#######################################

# If two or more valid 2024 values remain and their range is below
# 2 percentage points, retain all remaining values and calculate one
# municipi-level value using Mass_tonnes as weights.

Catalonia_Impropis_Low_Variation_Codi <-
  Catalonia_Impropis_Remaining_Variation %>%
  filter(
    Resolution_group ==
      "Weighted approximation (<2 pp range)"
  ) %>%
  pull(codi)


Catalonia_Impropis_Resolved_Weighted_Low_Variation <-
  Catalonia_Impropis_Manual_Review %>%
  filter(
    codi %in%
      Catalonia_Impropis_Low_Variation_Codi
  ) %>%
  group_by(
    codi,
    Catchment
  ) %>%
  summarise(
    n_source_circuits =
      n_distinct(Circuit),

    Impropis_percentage =
      weighted_mean_safe(
        Impropis_percentage,
        Mass_tonnes
      ),

    Mass_tonnes =
      sum_safe(
        Mass_tonnes
      ),

    Circuit =
      collapse_unique_values(
        Circuit
      ),

    Municipi_Impropis =
      collapse_unique_values(
        Municipi_Impropis,
        separator = " | "
      ),

    Municipi_key =
      first(Municipi_key),

    Municipis_original =
      collapse_unique_values(
        Municipis_original,
        separator = " | "
      ),

    Municipis_updated =
      first(Catchment),

    Collection_model =
      collapse_unique_values(
        Collection_model
      ),

    Catalan =
      collapse_unique_values(
        Catalan
      ),

    Comment =
      collapse_unique_values(
        Comment
      ),

    n_municipis_per_circuit_original =
      max(
        n_municipis_per_circuit_original,
        na.rm = TRUE
      ),

    resolved_by_individual_priority =
      any(
        resolved_by_individual_priority,
        na.rm = TRUE
      ),

    shared_circuit_reduced_to_one =
      any(
        shared_circuit_reduced_to_one,
        na.rm = TRUE
      ),

    .groups = "drop"
  ) %>%
  mutate(
    Relation_type =
      "Resolved_weighted_overlap",

    Identification_method =
      "Weighted aggregation of overlapping circuits (<2 pp range)",

    Decision_reason =
      paste(
        "At least two valid 2024 impurity values remained and",
        "their range was below",
        manual_review_difference_threshold_pp,
        "percentage points; circuit mass was used as weighting"
      ),

    resolution_iteration =
      NA_integer_,

    Mass_tonnes_scope =
      "Original circuit totals used as weights (not municipi-specific)",

    n_municipis_per_circuit =
      1L,

    n_circuits_per_municipi =
      n_source_circuits,

    resolved_by_manual_decision =
      FALSE,

    resolved_by_iterative_review =
      FALSE
  ) %>%
  select(
    Catchment,
    codi,
    Relation_type,
    Identification_method,
    Decision_reason,
    resolution_iteration,
    Circuit,
    Municipi_Impropis,
    Municipi_key,
    Municipis_original,
    Municipis_updated,
    Mass_tonnes,
    Mass_tonnes_scope,
    Impropis_percentage,
    Collection_model,
    Catalan,
    Comment,
    n_source_circuits,
    n_municipis_per_circuit_original,
    n_municipis_per_circuit,
    n_circuits_per_municipi,
    resolved_by_individual_priority,
    shared_circuit_reduced_to_one,
    resolved_by_manual_decision,
    resolved_by_iterative_review
  ) %>%
  arrange(Catchment)


#######################################
## 29D. Integrate direct and low-variation resolutions
#######################################

# Add the direct single-value assignments and low-variation weighted
# approximations to the resolved municipi table. Municipis with a range of
# at least 2 percentage points remain in the review table for the comparison
# prepared in Step 29E.

Catalonia_Impropis_Resolved_Final_Stage_Low <-
  bind_rows(
    Catalonia_Impropis_Resolved_Direct_Remaining,
    Catalonia_Impropis_Resolved_Weighted_Low_Variation
  ) %>%
  arrange(Catchment)


resolved_final_stage_low_codi <-
  Catalonia_Impropis_Resolved_Final_Stage_Low$codi


Catalonia_Impropis_Municipi_Simple <-
  Catalonia_Impropis_Municipi_Simple %>%
  filter(
    !(
      codi %in%
        resolved_final_stage_low_codi
    )
  ) %>%
  bind_rows(
    Catalonia_Impropis_Resolved_Final_Stage_Low
  ) %>%
  arrange(
    Catchment,
    Circuit
  )


Catalonia_Impropis_Manual_Review <-
  Catalonia_Impropis_Manual_Review %>%
  filter(
    !(
      codi %in%
        resolved_final_stage_low_codi
    )
  ) %>%
  recalculate_review_counts() %>%
  arrange(
    Catchment,
    Circuit
  )


#######################################
## 29E. Prepare remaining manual comparison
#######################################

# At this point the remaining review table contains the higher-variation
# overlaps that were not yet assigned in Step 29D. Their candidate 2024 values
# are placed side by side with the official 2020 municipi value.
#
# This table is retained permanently as an audit and plausibility-check table,
# even though these remaining 2024 values are subsequently aggregated in
# Step 29F.

Catalonia_Impropis_2020_Review_Lookup <-
  Catalonia %>%
  filter(
    Waste_Category == "Biowaste"
  ) %>%
  transmute(
    codi =
      as.character(codi),

    Impurities_percentage_2020
  ) %>%
  distinct(
    codi,
    .keep_all = TRUE
  )


Catalonia_Impropis_Manual_Review_Numbered <-
  Catalonia_Impropis_Manual_Review %>%
  group_by(
    codi,
    Catchment
  ) %>%
  arrange(
    Circuit,
    .by_group = TRUE
  ) %>%
  mutate(
    Candidate_number =
      row_number(),

    n_candidate_circuits =
      n_distinct(Circuit)
  ) %>%
  ungroup()


Catalonia_Impropis_Manual_Comparison <-
  Catalonia_Impropis_Manual_Review_Numbered %>%
  select(
    codi,
    Catchment,
    n_candidate_circuits,
    Candidate_number,
    Circuit,
    Municipis_updated,
    Impropis_percentage
  ) %>%
  pivot_wider(
    id_cols =
      c(
        codi,
        Catchment,
        n_candidate_circuits
      ),

    names_from =
      Candidate_number,

    values_from =
      c(
        Circuit,
        Municipis_updated,
        Impropis_percentage
      ),

    names_glue =
      "{.value}_{Candidate_number}"
  ) %>%
  rename_with(
    ~ str_replace(
      .x,
      "^Impropis_percentage_",
      "Impurities_2024_"
    )
  ) %>%
  left_join(
    Catalonia_Impropis_2020_Review_Lookup,
    by = "codi",
    relationship = "many-to-one"
  )


if (
  !(
    "Impurities_2024_1" %in%
      names(
        Catalonia_Impropis_Manual_Comparison
      )
  )
) {
  Catalonia_Impropis_Manual_Comparison$
    Impurities_2024_1 <- NA_real_
}


if (
  !(
    "Impurities_2024_2" %in%
      names(
        Catalonia_Impropis_Manual_Comparison
      )
  )
) {
  Catalonia_Impropis_Manual_Comparison$
    Impurities_2024_2 <- NA_real_
}


Catalonia_Impropis_Manual_Comparison <-
  Catalonia_Impropis_Manual_Comparison %>%
  mutate(
    Difference_2024_1_2_pp =
      round(
        abs(
          Impurities_2024_1 -
            Impurities_2024_2
        ),
        2
      ),

    Review_status =
      "Reviewed before weighted aggregation of remaining high-variation values"
  ) %>%
  relocate(
    Impurities_percentage_2020,
    .after = codi
  ) %>%
  arrange(
    desc(
      Difference_2024_1_2_pp
    ),
    Catchment
  )

Catalonia_Impropis_Manual_Comparison


#######################################
## 29F. Resolve remaining high-variation overlaps
#######################################

# After the comparison table has been stored, all remaining municipis with
# multiple valid 2024 values are also assigned a mass-weighted mean. The
# comparison from Step 29E is retained so these higher-variation assumptions
# can be reassessed later without reconstructing the original review table.

Catalonia_Impropis_Resolved_Weighted_High_Variation <-
  Catalonia_Impropis_Manual_Review %>%
  group_by(
    codi,
    Catchment
  ) %>%
  summarise(
    n_source_circuits =
      n_distinct(Circuit),

    Impropis_percentage =
      weighted_mean_safe(
        Impropis_percentage,
        Mass_tonnes
      ),

    Mass_tonnes =
      sum_safe(
        Mass_tonnes
      ),

    Circuit =
      collapse_unique_values(
        Circuit
      ),

    Municipi_Impropis =
      collapse_unique_values(
        Municipi_Impropis,
        separator = " | "
      ),

    Municipi_key =
      first(Municipi_key),

    Municipis_original =
      collapse_unique_values(
        Municipis_original,
        separator = " | "
      ),

    Municipis_updated =
      first(Catchment),

    Collection_model =
      collapse_unique_values(
        Collection_model
      ),

    Catalan =
      collapse_unique_values(
        Catalan
      ),

    Comment =
      collapse_unique_values(
        Comment
      ),

    n_municipis_per_circuit_original =
      max(
        n_municipis_per_circuit_original,
        na.rm = TRUE
      ),

    resolved_by_individual_priority =
      any(
        resolved_by_individual_priority,
        na.rm = TRUE
      ),

    shared_circuit_reduced_to_one =
      any(
        shared_circuit_reduced_to_one,
        na.rm = TRUE
      ),

    .groups = "drop"
  ) %>%
  mutate(
    Relation_type =
      "Resolved_weighted_overlap",

    Identification_method =
      "Weighted aggregation of overlapping circuits (>=2 pp range)",

    Decision_reason =
      paste(
        "Remaining 2024 impurity values differed by at least",
        manual_review_difference_threshold_pp,
        "percentage points; the values were reviewed in Step 29E",
        "and then combined using circuit mass as weighting"
      ),

    resolution_iteration =
      NA_integer_,

    Mass_tonnes_scope =
      "Original circuit totals used as weights (not municipi-specific)",

    n_municipis_per_circuit =
      1L,

    n_circuits_per_municipi =
      n_source_circuits,

    resolved_by_manual_decision =
      FALSE,

    resolved_by_iterative_review =
      FALSE
  ) %>%
  select(
    Catchment,
    codi,
    Relation_type,
    Identification_method,
    Decision_reason,
    resolution_iteration,
    Circuit,
    Municipi_Impropis,
    Municipi_key,
    Municipis_original,
    Municipis_updated,
    Mass_tonnes,
    Mass_tonnes_scope,
    Impropis_percentage,
    Collection_model,
    Catalan,
    Comment,
    n_source_circuits,
    n_municipis_per_circuit_original,
    n_municipis_per_circuit,
    n_circuits_per_municipi,
    resolved_by_individual_priority,
    shared_circuit_reduced_to_one,
    resolved_by_manual_decision,
    resolved_by_iterative_review
  ) %>%
  arrange(Catchment)

Catalonia_Impropis_Resolved_Weighted_High_Variation


#######################################
## 29G. Integrate high-variation weighted values
#######################################

# Add the weighted high-variation values to the resolved municipi table.
# The comparison table created in Step 29E remains unchanged for later review.
# After this integration, any remaining review rows represent cases for which
# no valid automatic value could be created.

resolved_high_variation_codi <-
  Catalonia_Impropis_Resolved_Weighted_High_Variation$codi


Catalonia_Impropis_Municipi_Simple <-
  Catalonia_Impropis_Municipi_Simple %>%
  filter(
    !(
      codi %in%
        resolved_high_variation_codi
    )
  ) %>%
  bind_rows(
    Catalonia_Impropis_Resolved_Weighted_High_Variation
  ) %>%
  arrange(
    Catchment,
    Circuit
  )


Catalonia_Impropis_Manual_Review <-
  Catalonia_Impropis_Manual_Review %>%
  filter(
    !(
      codi %in%
        resolved_high_variation_codi
    )
  ) %>%
  arrange(
    Catchment,
    Circuit
  )


#######################################
## 30. Summarise the final assignment status
#######################################

# This compact summary distinguishes the established assignment stages and the
# final direct and weighted resolutions from any cases still lacking a value.

Catalonia_Impropis_Final_Summary <- tibble(
  n_resolved_municipis =
    n_distinct(
      Catalonia_Impropis_Municipi_Simple$codi
    ),

  n_manually_resolved_municipis =
    n_distinct(
      Catalonia_Impropis_Resolved_Manual$codi
    ),

  n_iteratively_resolved_municipis =
    n_distinct(
      Catalonia_Impropis_Resolved_Iterative$codi
    ),

  n_direct_remaining_values =
    n_distinct(
      Catalonia_Impropis_Resolved_Direct_Remaining$codi
    ),

  n_weighted_low_variation_municipis =
    n_distinct(
      Catalonia_Impropis_Resolved_Weighted_Low_Variation$codi
    ),

  n_weighted_high_variation_municipis =
    n_distinct(
      Catalonia_Impropis_Resolved_Weighted_High_Variation$codi
    ),

  n_remaining_review_assignments =
    nrow(
      Catalonia_Impropis_Manual_Review
    ),

  n_remaining_review_municipis =
    n_distinct(
      Catalonia_Impropis_Manual_Review$codi
    )
)

Catalonia_Impropis_Final_Summary


#######################################
## 31. Run final assignment checks
#######################################

# The resolved and review tables must not overlap, the resolved table must
# contain one row per codi, and no circuit remaining in the review table may
# contain only one municipi after completion of the iterative procedure.

Catalonia_Impropis_Overlap_Check <-
  intersect(
    Catalonia_Impropis_Municipi_Simple$codi,
    Catalonia_Impropis_Manual_Review$codi
  )

Catalonia_Impropis_Overlap_Check


Catalonia_Impropis_Simple_Duplicates <-
  Catalonia_Impropis_Municipi_Simple %>%
  count(
    codi,
    name = "n_entries"
  ) %>%
  filter(
    n_entries > 1
  )

Catalonia_Impropis_Simple_Duplicates


Catalonia_Impropis_Manual_Type_Check <-
  Catalonia_Impropis_Manual_Review %>%
  count(Relation_type)

Catalonia_Impropis_Manual_Type_Check


Catalonia_Impropis_Remaining_Exclusive_Check <-
  Catalonia_Impropis_Manual_Review %>%
  filter(
    n_municipis_per_circuit == 1
  )

Catalonia_Impropis_Remaining_Exclusive_Check


#######################################
## 32. Check assignment outcomes after model selection
#######################################

# Summarise whether municipis with selected source rows reached the resolved or
# remaining-review tables. This is a general check and does not depend on a
# hard-coded list of municipis.

Catalonia_Impropis_Model_Assignment_Outcome <-
  Catalonia_Impropis_Model_Selection %>%
  filter(
    Use_for_assignment,
    !is.na(codi)
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_system_2024
  ) %>%
  mutate(
    Assignment_outcome = case_when(
      codi %in%
        Catalonia_Impropis_Municipi_Simple$codi ~
        "Resolved",

      codi %in%
        Catalonia_Impropis_Manual_Review$codi ~
        "Remaining manual review",

      TRUE ~
        "Selected source row but no final assignment"
    )
  ) %>%
  arrange(
    Assignment_outcome,
    Catchment
  )

Catalonia_Impropis_Model_Assignment_Outcome


#######################################
## 33. Create the final Impropis lookup
#######################################

# Only the final resolved municipi table is used for the merge. The lookup
# contains one codi and one impurity value per municipi; unresolved review
# cases are intentionally omitted.

Catalonia_Impropis_Lookup <-
  Catalonia_Impropis_Municipi_Simple %>%
  transmute(
    codi_join =
      as.character(codi),

    Impropis_percentage_join =
      Impropis_percentage
  ) %>%
  filter(
    !is.na(codi_join),
    !is.na(Impropis_percentage_join)
  ) %>%
  distinct()


Catalonia_Impropis_Lookup_Duplicates <-
  Catalonia_Impropis_Lookup %>%
  count(
    codi_join,
    name = "n_values"
  ) %>%
  filter(
    n_values > 1
  )

Catalonia_Impropis_Lookup_Duplicates


#######################################
## 34. Define collection systems without impurity data
#######################################

# No conventional impurity measurement is applicable to municipis without
# separate collection or using only community composting. The same exclusion
# is used in the merge and in all subsequent coverage checks.

excluded_impropis_systems <- c(
  "No separate collection",
  "Community composting"
)


#######################################
## 35. Merge Impropis into Catalonia
#######################################

# Join resolved values to the main dataset by codi. Values are written only to
# Biowaste rows with an eligible separate collection system; all other rows
# remain NA in the existing placeholder column.

Catalonia_Merged_Impropis <- Catalonia %>%
  mutate(
    codi_join =
      as.character(codi),

    Impurities_percentage_2024 =
      NA_real_
  ) %>%
  left_join(
    Catalonia_Impropis_Lookup,
    by = "codi_join",
    relationship = "many-to-one"
  ) %>%
  mutate(
    Impurities_percentage_2024 = if_else(
      Waste_Category == "Biowaste" &
        !is.na(Collection_system_2024) &
        !(
          Collection_system_2024 %in%
            excluded_impropis_systems
        ),
      Impropis_percentage_join,
      NA_real_,
      missing = NA_real_
    )
  ) %>%
  select(
    -codi_join,
    -Impropis_percentage_join
  )


#######################################
## 36. Check the merged dataset
#######################################

# Assess coverage only among municipis with an eligible separate collection
# system. Additional checks list relevant municipis still lacking a value and
# confirm that excluded systems did not receive an impurity value.

Catalonia_Impropis_Merge_Summary <-
  Catalonia_Merged_Impropis %>%
  filter(
    Waste_Category == "Biowaste"
  ) %>%
  summarise(
    n_biowaste_municipis =
      n_distinct(codi),

    n_excluded_municipis =
      n_distinct(
        codi[
          Collection_system_2024 %in%
            excluded_impropis_systems
        ]
      ),

    n_eligible_municipis =
      n_distinct(
        codi[
          !is.na(Collection_system_2024) &
            !(
              Collection_system_2024 %in%
                excluded_impropis_systems
            )
        ]
      ),

    n_eligible_municipis_with_impropis =
      n_distinct(
        codi[
          !is.na(Collection_system_2024) &
            !(
              Collection_system_2024 %in%
                excluded_impropis_systems
            ) &
            !is.na(
              Impurities_percentage_2024
            )
        ]
      ),

    n_eligible_municipis_without_impropis =
      n_eligible_municipis -
        n_eligible_municipis_with_impropis
  )

Catalonia_Impropis_Merge_Summary


Catalonia_Impropis_Missing <-
  Catalonia_Merged_Impropis %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(Collection_system_2024),
    !(
      Collection_system_2024 %in%
        excluded_impropis_systems
    ),
    is.na(Impurities_percentage_2024)
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_system_2024
  ) %>%
  arrange(Catchment)

Catalonia_Impropis_Missing


Catalonia_Impropis_Excluded_System_Check <-
  Catalonia_Merged_Impropis %>%
  filter(
    Waste_Category == "Biowaste",
    Collection_system_2024 %in%
      excluded_impropis_systems,
    !is.na(Impurities_percentage_2024)
  )

Catalonia_Impropis_Excluded_System_Check


Catalonia_Impropis_Not_Matched <-
  Catalonia_Impropis_Lookup %>%
  anti_join(
    Catalonia %>%
      transmute(
        codi_join =
          as.character(codi)
      ) %>%
      distinct(),
    by = "codi_join"
  )

Catalonia_Impropis_Not_Matched


#######################################
## 37. Export the final datasets
#######################################

# Export only after all automatic, model-based, manual, iterative, and final
# weighted decisions have been integrated. The high-variation comparison table
# from Step 29E is retained as an audit for later reassessment. Additional audit
# tables document excluded large-producer records, source-row collection-model
# decisions, excluded source rows, and municipis without a valid model-based
# assignment. UTF-8 with BOM preserves Catalan characters in Excel, while
# semicolon-separated write_delim retains decimal points for numeric values.

write_utf8_bom_csv(
  Catalonia_Impropis_Municipi_Simple,
  file.path(
    output_directory,
    "Catalonia_Impropis_Municipi_Simple.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Manual_Review,
  file.path(
    output_directory,
    "Catalonia_Impropis_Manual_Review.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Resolved_By_Priority,
  file.path(
    output_directory,
    "Catalonia_Impropis_Resolved_By_Priority.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Resolved_Manual,
  file.path(
    output_directory,
    "Catalonia_Impropis_Resolved_Manual.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Resolved_Iterative,
  file.path(
    output_directory,
    "Catalonia_Impropis_Resolved_Iterative.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Resolved_Direct_Remaining,
  file.path(
    output_directory,
    "Catalonia_Impropis_Resolved_Direct_Remaining.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Resolved_Weighted_Low_Variation,
  file.path(
    output_directory,
    "Catalonia_Impropis_Resolved_Weighted_Low_Variation.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Manual_Comparison,
  file.path(
    output_directory,
    paste0(
      "Catalonia_Impropis_Manual_Review_",
      "Comparison_2020_2024.csv"
    )
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Resolved_Weighted_High_Variation,
  file.path(
    output_directory,
    "Catalonia_Impropis_Resolved_Weighted_High_Variation.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Iterative_Removed_Shared_Assignments,
  file.path(
    output_directory,
    paste0(
      "Catalonia_Impropis_Iterative_",
      "Removed_Shared_Assignments.csv"
    )
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Large_Producers,
  file.path(
    output_directory,
    "Catalonia_Impropis_Excluded_Large_Producers.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Collection_Model_Check,
  file.path(
    output_directory,
    "Catalonia_Impropis_Collection_Model_Check.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Collection_Model_Excluded,
  file.path(
    output_directory,
    "Catalonia_Impropis_Excluded_Collection_Model_Rows.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Collection_Model_No_Assignment,
  file.path(
    output_directory,
    "Catalonia_Impropis_Collection_Model_No_Assignment.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Impropis_Model_Assignment_Outcome,
  file.path(
    output_directory,
    "Catalonia_Impropis_Model_Assignment_Outcome.csv"
  )
)


write_utf8_bom_csv(
  Catalonia_Merged_Impropis,
  file.path(
    output_directory,
    paste0(
      "BRIT_Katalonien_2024_",
      "merged_datasets_incl_impropis.csv"
    )
  )
)
