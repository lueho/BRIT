source("R/bootstrap.R")

###############
### Packages
###############

library(tidyverse)
library(ggpubr)
library(grid)
library(effectsize)
library(patchwork)


###############
### Helpers
###############

source(
  brit_path(
    "R",
    "helpers.R"
  )
)



###############################
### Fonts and theme
###############################

if (.Platform$OS.type == "windows") {
  windowsFonts(
    Calibri = windowsFont("Calibri")
  )
}

theme_set(theme_plot)




################
### Raw data (excl green waste)
################

RLP <- read.csv(
  file = brit_path(
    "data",
    "raw",
    "RLP",
    "BRIT_Deutschland_Rheinland-Pfalz_2024.csv"
  ),
  na.strings = c("", "#NV"),
  header = TRUE,
  sep = ";",
  dec = ".",
  fileEncoding = "Windows-1252"
) %>%
  filter(
    is.na(Waste_Category) |
      Waste_Category != "Green waste"
  )


#########################################################
### Prepare KPIs
#########################################################

################################
### Numeric data preparation
################################

RLP <- RLP %>%
  mutate(
    BW_RW_kg = parse_double(
      as.character(BW_RW_kg),
      locale = locale(
        decimal_mark = "."
      ),
      na = c(
        "",
        "#NV"
      )
    )
  )


################################
### Separation rates
################################

calculate_sr <- function(
    biowaste_values,
    residual_values,
    waste_category
) {
  
  biowaste_value <- biowaste_values[
    waste_category == "Biowaste" &
      !is.na(biowaste_values)
  ] %>%
    unique()
  
  residual_value <- residual_values[
    waste_category == "Residual waste" &
      !is.na(residual_values)
  ] %>%
    unique()
  
  sr <- if (
    length(biowaste_value) == 1 &&
    length(residual_value) == 1 &&
    biowaste_value + residual_value > 0
  ) {
    round(
      biowaste_value /
        (biowaste_value + residual_value) *
        100,
      2
    )
  } else {
    NA_real_
  }
  
  if_else(
    waste_category %in% c(
      "Biowaste",
      "Residual waste"
    ),
    sr,
    NA_real_
  )
}


RLP <- RLP %>%
  group_by(NUTS_LAU) %>%
  mutate(
    across(
      .cols = all_of(
        paste0(
          "Specific_Waste_kg_",
          2021:2024
        )
      ),
      .fns = ~ calculate_sr(
        biowaste_values = .x,
        residual_values = .x,
        waste_category = Waste_Category
      ),
      .names = "SR_{.col}"
    ),
    
    SR_approxBW_2024 = calculate_sr(
      biowaste_values = Specific_Waste_kg_2024,
      residual_values = BW_RW_kg,
      waste_category = Waste_Category
    )
  ) %>%
  ungroup() %>%
  rename_with(
    .fn = ~ str_remove(
      .x,
      "Specific_Waste_kg_"
    ),
    .cols = starts_with(
      "SR_Specific_Waste_kg_"
    )
  ) %>%
  relocate(
    SR_2021,
    SR_2022,
    SR_2023,
    SR_2024,
    SR_approxBW_2024,
    .after = FWtot_RW_kg
  )




########################################################
### Prepare IFs
########################################################

######################################
### Collection frequencies & counts
######################################





RLP <- RLP %>%
  mutate(
    Frequency_clean = Frequency %>%
      str_squish() %>%
      na_if(""),
    
    # General frequency structure before the first semicolon
    Frequency_structure = Frequency_clean %>%
      str_extract("^[^;]+") %>%
      str_trim(),
    
    # Relevant part containing the standard annual frequency
    Frequency_relevant = case_when(
      is.na(Frequency_clean) ~ NA_character_,
      
      str_to_lower(Frequency_structure) == "flexible" ~
        str_match(
          Frequency_clean,
          regex(
            "Standard:\\s*(.*?)(?:;\\s*Optional:|$)",
            ignore_case = TRUE
          )
        )[, 2],
      
      TRUE ~ str_remove(
        Frequency_clean,
        "^[^;]+;\\s*"
      )
    ),
    
    # Extract all annual standard values
    Frequency_values = str_extract_all(
      Frequency_relevant,
      regex(
        "\\d+(?=\\s*per\\s*year)",
        ignore_case = TRUE
      )
    ),
    
    Frequency_n_values = map_int(
      Frequency_values,
      ~ sum(!is.na(.x))
    ),
    
    # Only assign a value if exactly one standard value was found
    Frequency_per_year = map_int(
      Frequency_values,
      ~ {
        values <- .x[!is.na(.x)]
        
        if (length(values) == 1) {
          as.integer(values)
        } else {
          NA_integer_
        }
      }
    ),
    
    # Flag entries that require manual review
    Frequency_check = case_when(
      Frequency_n_values > 1 ~ paste0(
        "Check standard values: ",
        map_chr(
          Frequency_values,
          ~ paste(.x[!is.na(.x)], collapse = ", ")
        )
      ),
      
      !is.na(Frequency_clean) &
        Frequency_n_values == 0 ~
        "Check: no annual frequency found",
      
      TRUE ~ NA_character_
    )
  ) %>%
  select(
    -Frequency_clean,
    -Frequency_relevant,
    -Frequency_values,
    -Frequency_n_values
  ) %>%
  relocate(
    Frequency_structure,
    Frequency_per_year,
    Frequency_check,
    .after = Frequency
  )


########################################
### Biowaste-to-residual frequency ratio
########################################

RLP <- RLP %>%
  group_by(NUTS_LAU) %>%
  mutate(
    Collection_count_ratio = {
      biowaste_frequency <- Frequency_per_year[
        Waste_Category == "Biowaste" &
          !is.na(Frequency_per_year)
      ] %>%
        unique()
      
      residual_frequency <- Frequency_per_year[
        Waste_Category == "Residual waste" &
          !is.na(Frequency_per_year)
      ] %>%
        unique()
      
      ratio <- if (
        length(biowaste_frequency) == 1 &&
        length(residual_frequency) == 1 &&
        residual_frequency != 0
      ) {
        round(
          biowaste_frequency / residual_frequency,
          2
        )
      } else {
        NA_real_
      }
      
      if_else(
        Waste_Category %in% c(
          "Biowaste",
          "Residual waste"
        ),
        ratio,
        NA_real_
      )
    }
  ) %>%
  ungroup() %>%
  relocate(
    Collection_count_ratio,
    .after = Frequency_per_year
  )



############################
### Export processed data
############################

dir.create(
  brit_path(
    "data",
    "processed",
    "RLP"
  ),
  recursive = TRUE,
  showWarnings = FALSE
)

write.table(
  RLP,
  file = brit_path(
    "data",
    "processed",
    "RLP",
    "BRIT_Deutschland_Rheinland-Pfalz_2024_processed.csv"
  ),
  sep = ";",
  dec = ".",
  na = "",
  row.names = FALSE,
  col.names = TRUE,
  quote = TRUE,
  fileEncoding = "Windows-1252"
)


#############################################################################################################################
### Überarbeiteten Datensatz einlesen
#############################################################################################################################

RLP <- read.csv(
  file = brit_path(
    "data",
    "processed",
    "RLP",
    "BRIT_Deutschland_Rheinland-Pfalz_2024_processed.csv"
  ),
  na.strings = "",
  header = TRUE,
  sep = ";",
  dec = ".",
  fileEncoding = "Windows-1252"
)


#######################################
### Basic data preparation
#######################################

RLP <- RLP %>%
  mutate(
    Frequency_structure = factor(
      Frequency_structure %>%
        as.character() %>%
        str_squish() %>%
        na_if(""),
      levels = c(
        "Fixed",
        "Fixed-Seasonal",
        "Flexible"
      )
    ),
    Frequency_per_year = parse_double(
      as.character(Frequency_per_year),
      locale = locale(
        decimal_mark = "."
      ),
      na = c(
        "",
        "NA"
      )
    ),
    Collection_count_ratio = parse_double(
      as.character(Collection_count_ratio),
      locale = locale(
        decimal_mark = "."
      ),
      na = c(
        "",
        "NA"
      )
    )
  )


RLP_BW_base <- RLP %>%
  filter(
    Waste_Category == "Biowaste"
  )


RLP_RW_base <- RLP %>%
  filter(
    Waste_Category == "Residual waste"
  )



#######################################
### Descriptive statistics
#######################################

#####################
### KPIs
#####################

# Biowaste quantities

RLP_BW_summary <- RLP_BW_base %>%
  summary_statistics(
    summary_var = "Specific_Waste_kg_2024",
    digits = 1
  )

RLP_BW_summary


# Residual waste quantities

RLP_RW_summary <- RLP_RW_base %>%
  summary_statistics(
    summary_var = "Specific_Waste_kg_2024",
    digits = 1
  )

RLP_RW_summary


# Biowaste in the residual waste stream

RLP_BW_RW_summary <- RLP_RW_base %>%
  distinct(
    NUTS_LAU,
    BW_RW_kg
  ) %>%
  summary_statistics(
    summary_var = "BW_RW_kg",
    digits = 1
  )

RLP_BW_RW_summary


# unpacked food waste in residual waste

RLP_FWunpack_RW_summary <- RLP_RW_base %>%
  distinct(
    NUTS_LAU,
    FWunpack_RW_kg
  ) %>%
  summary_statistics(
    summary_var = "FWunpack_RW_kg",
    digits = 1
  )

RLP_FWunpack_RW_summary


# total food waste in residual waste

RLP_FWtot_RW_summary <- RLP_RW_base %>%
  distinct(
    NUTS_LAU,
    FWtot_RW_kg
  ) %>%
  summary_statistics(
    summary_var = "FWtot_RW_kg",
    digits = 1
  )

RLP_FWtot_RW_summary





# Separation rate

RLP_SR_summary <- RLP_BW_base %>%
  distinct(
    NUTS_LAU,
    SR_2024
  ) %>%
  summary_statistics(
    summary_var = "SR_2024"
  )

RLP_SR_summary


# Approximated biowaste separation rate

RLP_SR_approxBW_summary <- RLP_BW_base %>%
  distinct(
    NUTS_LAU,
    SR_approxBW_2024
  ) %>%
  summary_statistics(
    summary_var = "SR_approxBW_2024"
  )

RLP_SR_approxBW_summary


#######################################
### Overall approximated biowaste
### separation rate for RLP
#######################################

RLP_SR_approxBW_total_data <- RLP %>%
  filter(
    Waste_Category %in% c(
      "Biowaste",
      "Residual waste"
    )
  ) %>%
  group_by(NUTS_LAU) %>%
  summarise(
    Population_2024 = first(
      Population_2024[
        !is.na(Population_2024)
      ],
      default = NA_real_
    ),
    Biowaste_kg_per_capita = first(
      Specific_Waste_kg_2024[
        Waste_Category == "Biowaste" &
          !is.na(Specific_Waste_kg_2024)
      ],
      default = NA_real_
    ),
    Biowaste_in_RW_kg_per_capita = first(
      BW_RW_kg[
        Waste_Category == "Residual waste" &
          !is.na(BW_RW_kg)
      ],
      default = NA_real_
    ),
    .groups = "drop"
  ) %>%
  filter(
    !is.na(Population_2024),
    Population_2024 > 0,
    !is.na(Biowaste_kg_per_capita),
    !is.na(Biowaste_in_RW_kg_per_capita)
  ) %>%
  mutate(
    Biowaste_total_kg =
      Biowaste_kg_per_capita *
      Population_2024,
    
    Biowaste_in_RW_total_kg =
      Biowaste_in_RW_kg_per_capita *
      Population_2024
  )


RLP_SR_approxBW_total <- RLP_SR_approxBW_total_data %>%
  summarise(
    n_collection_areas = n(),
    population_covered = sum(
      Population_2024
    ),
    Biowaste_total_kg = sum(
      Biowaste_total_kg
    ),
    Biowaste_in_RW_total_kg = sum(
      Biowaste_in_RW_total_kg
    ),
    SR_approxBW_2024_total = round(
      Biowaste_total_kg /
        (
          Biowaste_total_kg +
            Biowaste_in_RW_total_kg
        ) *
        100,
      2
    )
  )

RLP_SR_approxBW_total



#######################################
### Municipalities and population
### above/below 50% separation rate
#######################################

RLP_SR_50_distribution <- RLP_BW_base %>%
  filter(
    !is.na(SR_2024)
  ) %>%
  distinct(
    NUTS_LAU,
    Population_2024,
    Population_Density_2024,
    SR_2024
  ) %>%
  mutate(
    SR_50_category = factor(
      if_else(
        SR_2024 > 50,
        "> 50%",
        "≤ 50%"
      ),
      levels = c(
        "≤ 50%",
        "> 50%"
      )
    )
  ) %>%
  summarise_population_distribution(
    category_var = "SR_50_category",
    area_var = "NUTS_LAU",
    population_var = "Population_2024",
    density_var = "Population_Density_2024",
    sort_by = "category"
  )

RLP_SR_50_distribution



#######################################
### Municipalities and population
### above/below 50% approximated
### biowaste separation rate
#######################################

RLP_SR_approxBW_50_distribution <- RLP_BW_base %>%
  filter(
    !is.na(SR_approxBW_2024)
  ) %>%
  distinct(
    NUTS_LAU,
    Population_2024,
    Population_Density_2024,
    SR_approxBW_2024
  ) %>%
  mutate(
    SR_approxBW_50_category = factor(
      if_else(
        SR_approxBW_2024 > 50,
        "> 50%",
        "≤ 50%"
      ),
      levels = c(
        "≤ 50%",
        "> 50%"
      )
    )
  ) %>%
  summarise_population_distribution(
    category_var = "SR_approxBW_50_category",
    area_var = "NUTS_LAU",
    population_var = "Population_2024",
    density_var = "Population_Density_2024",
    sort_by = "category"
  )

RLP_SR_approxBW_50_distribution




##########################################################
### Influencing Factors
##########################################################

##############################
### IF: Collection mode
##############################

RLP_sepcol <- RLP %>%
  filter(
    Waste_Category %in% c("Food waste", "Biowaste"),
    !is.na(Collection_System),
    Collection_System != ""
  ) %>%
  summarise_population_distribution(
    category_var = "Collection_System",
    sort_by = "entries_desc"
  )

RLP_sepcol


#######################################
### Collection count clusters
#######################################

RLP <- RLP %>%
  mutate(
    Collection_count_cluster = case_when(
      is.na(Frequency_per_year) ~ NA_character_,
      Frequency_per_year < 13 ~ "< 13",
      Frequency_per_year == 13 ~ "13",
      Frequency_per_year == 18 ~ "18",
      Frequency_per_year == 26 ~ "26",
      between(Frequency_per_year, 27, 38) ~ "27–38",
      between(Frequency_per_year, 39, 51) ~ "39–51",
      Frequency_per_year == 52 ~ "52",
      Frequency_per_year > 52 ~ "> 52",
      TRUE ~ NA_character_
    ),
    Collection_count_cluster = factor(
      Collection_count_cluster,
      levels = c(
        "< 13",
        "13",
        "18",
        "26",
        "27–38",
        "39–51",
        "52",
        "> 52"
      )
    )
  )


#######################################
### Door-to-door base data
#######################################

RLP_BW_DtD <- RLP %>%
  filter(
    Waste_Category %in% c(
      "Food waste",
      "Biowaste"
    ),
    Collection_System == "Door to door"
  )


RLP_RW_DtD <- RLP %>%
  filter(
    Waste_Category == "Residual waste",
    Collection_System == "Door to door"
  )





##############################
### IF: Frequency structure
##############################

# Biowaste

RLP_BW_FS <- RLP_BW_DtD %>%
  filter(
    !is.na(Frequency_structure)
  ) %>%
  summarise_population_distribution(
    category_var = "Frequency_structure",
    sort_by = "entries_desc"
  )

RLP_BW_FS


# Residual waste

RLP_RW_FS <- RLP_RW_DtD %>%
  filter(
    !is.na(Frequency_structure)
  ) %>%
  summarise_population_distribution(
    category_var = "Frequency_structure",
    sort_by = "entries_desc"
  )

RLP_RW_FS


##############################
### IF: Collection count
##############################

# Biowaste

RLP_BW_CC <- RLP_BW_DtD %>%
  filter(
    !is.na(Collection_count_cluster)
  ) %>%
  summarise_population_distribution(
    category_var = "Collection_count_cluster",
    sort_by = "category"
  )

RLP_BW_CC


# Residual waste

RLP_RW_CC <- RLP_RW_DtD %>%
  filter(
    !is.na(Collection_count_cluster)
  ) %>%
  summarise_population_distribution(
    category_var = "Collection_count_cluster",
    sort_by = "category"
  )

RLP_RW_CC




##############################
### IF: Collection count ratio
##############################

#######################################
### Collection count ratio clusters
#######################################

RLP <- RLP %>%
  mutate(
    Collection_count_ratio_cluster = case_when(
      is.na(Collection_count_ratio) ~ NA_character_,
      near(
        Collection_count_ratio,
        1
      ) ~ "1",
      Collection_count_ratio > 1 &
        Collection_count_ratio < 2 ~
        "> 1 and < 2",
      Collection_count_ratio >= 2 ~
        ">= 2",
      TRUE ~ NA_character_
    ),
    Collection_count_ratio_cluster = factor(
      Collection_count_ratio_cluster,
      levels = c(
        "1",
        "> 1 and < 2",
        ">= 2"
      )
    )
  )


#######################################
### IF: Summary
#######################################

RLP_CC_ratio <- RLP %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(Collection_count_ratio_cluster)
  ) %>%
  distinct(
    NUTS_LAU,
    Collection_count_ratio_cluster,
    Population_2024
  ) %>%
  summarise_population_distribution(
    category_var = "Collection_count_ratio_cluster",
    sort_by = "category"
  )

RLP_CC_ratio




##################################################################################
### Linear correlation and regression - Comparison of separation rates 
###################################################################################

#######################################
### Data preparation
#######################################

RLP_SR_comparison <- RLP_BW_base %>%
  filter(
    !is.na(SR_2024),
    !is.na(SR_approxBW_2024)
  ) %>%
  distinct(
    NUTS_LAU,
    SR_2024,
    SR_approxBW_2024
  )


########################################
### Linear correlation and regression  
#######################################

RLP_SR_relation <- run_scatter_lm_test(
  data = RLP_SR_comparison,
  x = "SR_2024",
  y = "SR_approxBW_2024",
  digits = 2
)

RLP_SR_relation$cor_result

summary(
  RLP_SR_relation$lm_model
)


#######################################
### Scatter plot
#######################################

gg_RLP_SR_correlation <- ggplot(
  RLP_SR_relation$data,
  aes(
    x = SR_2024,
    y = SR_approxBW_2024
  )
) +
  geom_point(
    shape = 21,
    fill = "transparent",
    color = "black",
    size = 4,
    stroke = 1.2
  ) +
  geom_smooth(
    method = "lm",
    formula = y ~ x,
    se = FALSE,
    color = "black",
    linewidth = 1.5
  ) +
  add_scatter_lm_labels(
    labels = RLP_SR_relation$labels,
    slope = RLP_SR_relation$slope,
    position = "auto",
    x_left = 2
  ) +
  scale_x_continuous(
    breaks = seq(
      0,
      100,
      by = 20
    ),
    expand = c(0, 0)
  ) +
  scale_y_continuous(
    breaks = seq(
      0,
      100,
      by = 20
    ),
    expand = c(0, 0)
  ) +
  coord_cartesian(
    xlim = c(0, 102),
    ylim = c(0, 102),
    expand = FALSE
  ) +
  labs(
    x = "Biowaste stream separation rate [%]",
    y = "Aprx. net biowaste separation rate [%]"
  ) +
  theme_plot

gg_RLP_SR_correlation


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "RLP",
    "Gross vs approximated net biowaste separation rate_RLP.png"
  ),
  plot = gg_RLP_SR_correlation,
  width = 16,
  height = 9,
  dpi = 300
)



############################################################################
### Statistical assessment KPI vs IF - Collection count ratio 
############################################################################


##################################################
### KPI 1: Biowaste quantities
##################################################

#####################
### Data preparation
#####################

RLP_CC_ratio_BW <- RLP %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(Specific_Waste_kg_2024),
    !is.na(Collection_count_ratio_cluster)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Collection_count_ratio_cluster,
    Population_2024,
    Specific_Waste_kg_2024
  ) %>%
  mutate(
    Collection_count_ratio_cluster = droplevels(
      Collection_count_ratio_cluster
    )
  )

RLP_CC_ratio_BW


#######################################
### Summary
#######################################

RLP_CC_ratio_BW_summary <- RLP_CC_ratio_BW %>%
  summary_statistics(
    summary_var = "Specific_Waste_kg_2024",
    group_var = "Collection_count_ratio_cluster",
    digits = 2
  )

RLP_CC_ratio_BW_summary


#######################################
### ANOVA
#######################################

anova_CC_ratio_BW <- run_oneway_test(
  data = RLP_CC_ratio_BW,
  response = "Specific_Waste_kg_2024",
  group = "Collection_count_ratio_cluster"
)


# Levene test

anova_CC_ratio_BW$levene_result

anova_CC_ratio_BW$levene_p


# Selected ANOVA method

anova_CC_ratio_BW$anova_method

anova_CC_ratio_BW$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_CC_ratio_BW <- run_pairwise_t_test(
  data = RLP_CC_ratio_BW,
  response = "Specific_Waste_kg_2024",
  group = "Collection_count_ratio_cluster",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_CC_ratio_BW


pairwise_CC_ratio_BW_plot <- pairwise_CC_ratio_BW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_CC_ratio_BW <- effectsize::eta_squared(
  anova_CC_ratio_BW$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_CC_ratio_BW


eta2_label_CC_ratio_BW <- paste0(
  "η² = ",
  round(
    eta2_CC_ratio_BW$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_CC_ratio_BW <- format_anova_label(
  p = anova_CC_ratio_BW$anova_p,
  method = anova_CC_ratio_BW$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_CC_ratio_BW


#######################################
### Y-axis preparation
#######################################

y_interval_CC_ratio_BW <- 50
y_break_max_CC_ratio_BW <- 230
y_max_CC_ratio_BW <- 235

n_label_y_CC_ratio_BW <- 200

significance_y_CC_ratio_BW <- c(
  235,
  245,
  255
)[
  seq_len(
    nrow(pairwise_CC_ratio_BW_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_CC_ratio_BW <- ggplot(
  RLP_CC_ratio_BW,
  aes(
    x = Collection_count_ratio_cluster,
    y = Specific_Waste_kg_2024
  )
) +
  geom_boxplot(
    fill = "transparent",
    color = "black",
    linewidth = 1.5
  ) +
  stat_summary(
    fun = mean,
    geom = "point",
    shape = 4,
    size = 8,
    color = "black"
  ) +
  add_plot_label(
    label = anova_label_CC_ratio_BW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_CC_ratio_BW,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_CC_ratio_BW,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_CC_ratio_BW_plot,
    y_positions = significance_y_CC_ratio_BW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CC_ratio_BW,
      by = y_interval_CC_ratio_BW
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_CC_ratio_BW
    )
  ) +
  labs(
    x = "Annual collection counts ratio of biowaste to residual waste",
    y = bquote("Biowaste [" *kg ~ inh^{-1} ~ a^{-1} *"]")
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_CC_ratio_BW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "RLP",
    "Collection count ratio on biowaste quantities_RLP.png"
  ),
  plot = gg_CC_ratio_BW,
  width = 16,
  height = 9,
  dpi = 300
)


##################################################
### KPI 2: Residual waste quantities
##################################################

#####################
### Data preparation
#####################

RLP_CC_ratio_RW <- RLP %>%
  filter(
    Waste_Category == "Residual waste",
    !is.na(Specific_Waste_kg_2024),
    !is.na(Collection_count_ratio_cluster)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Collection_count_ratio_cluster,
    Population_2024,
    Specific_Waste_kg_2024
  ) %>%
  mutate(
    Collection_count_ratio_cluster = droplevels(
      Collection_count_ratio_cluster
    )
  )

RLP_CC_ratio_RW


#######################################
### Summary
#######################################

RLP_CC_ratio_RW_summary <- RLP_CC_ratio_RW %>%
  summary_statistics(
    summary_var = "Specific_Waste_kg_2024",
    group_var = "Collection_count_ratio_cluster",
    digits = 2
  )

RLP_CC_ratio_RW_summary


#######################################
### ANOVA
#######################################

anova_CC_ratio_RW <- run_oneway_test(
  data = RLP_CC_ratio_RW,
  response = "Specific_Waste_kg_2024",
  group = "Collection_count_ratio_cluster"
)


# Levene test

anova_CC_ratio_RW$levene_result

anova_CC_ratio_RW$levene_p


# Selected ANOVA method

anova_CC_ratio_RW$anova_method

anova_CC_ratio_RW$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_CC_ratio_RW <- run_pairwise_t_test(
  data = RLP_CC_ratio_RW,
  response = "Specific_Waste_kg_2024",
  group = "Collection_count_ratio_cluster",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_CC_ratio_RW


pairwise_CC_ratio_RW_plot <- pairwise_CC_ratio_RW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_CC_ratio_RW <- effectsize::eta_squared(
  anova_CC_ratio_RW$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_CC_ratio_RW


eta2_label_CC_ratio_RW <- paste0(
  "η² = ",
  round(
    eta2_CC_ratio_RW$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_CC_ratio_RW <- format_anova_label(
  p = anova_CC_ratio_RW$anova_p,
  method = anova_CC_ratio_RW$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_CC_ratio_RW



#######################################
### Y-axis preparation
#######################################

y_interval_CC_ratio_RW <- 50
y_break_max_CC_ratio_RW <- 250
y_max_CC_ratio_RW <- 260

n_label_y_CC_ratio_RW <- 220

significance_y_CC_ratio_RW <- c(
  325,
  340,
  355
)[
  seq_len(
    nrow(pairwise_CC_ratio_RW_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_CC_ratio_RW <- ggplot(
  RLP_CC_ratio_RW,
  aes(
    x = Collection_count_ratio_cluster,
    y = Specific_Waste_kg_2024
  )
) +
  geom_boxplot(
    fill = "transparent",
    color = "black",
    linewidth = 1.5
  ) +
  stat_summary(
    fun = mean,
    geom = "point",
    shape = 4,
    size = 8,
    color = "black"
  ) +
  add_plot_label(
    label = anova_label_CC_ratio_RW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_CC_ratio_RW,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_CC_ratio_RW,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_CC_ratio_RW_plot,
    y_positions = significance_y_CC_ratio_RW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CC_ratio_RW,
      by = y_interval_CC_ratio_RW
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_CC_ratio_RW
    )
  ) +
  labs(
    x = "Annual collection counts ratio of biowaste to residual waste",
    y = bquote(
      "Residual waste [" *
        kg ~ inh^{-1} ~ a^{-1} *
        "]"
    )
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_CC_ratio_RW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "RLP",
    "Collection count ratio on residual waste quantities_RLP.png"
  ),
  plot = gg_CC_ratio_RW,
  width = 16,
  height = 9,
  dpi = 300
)





##################################################
### KPI 3a: Biowaste stream separation rate
##################################################

#####################
### Data preparation
#####################

RLP_CC_ratio_SR <- RLP %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(SR_2024),
    !is.na(Collection_count_ratio_cluster)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Collection_count_ratio_cluster,
    Population_2024,
    SR_2024
  ) %>%
  mutate(
    Collection_count_ratio_cluster = droplevels(
      Collection_count_ratio_cluster
    )
  )

RLP_CC_ratio_SR


#######################################
### Summary
#######################################

RLP_CC_ratio_SR_summary <- RLP_CC_ratio_SR %>%
  summary_statistics(
    summary_var = "SR_2024",
    group_var = "Collection_count_ratio_cluster",
    digits = 2
  )

RLP_CC_ratio_SR_summary


#######################################
### ANOVA
#######################################

anova_CC_ratio_SR <- run_oneway_test(
  data = RLP_CC_ratio_SR,
  response = "SR_2024",
  group = "Collection_count_ratio_cluster"
)


# Levene test

anova_CC_ratio_SR$levene_result

anova_CC_ratio_SR$levene_p


# Selected ANOVA method

anova_CC_ratio_SR$anova_method

anova_CC_ratio_SR$anova_result



#######################################
### Pairwise t-tests
#######################################

pairwise_CC_ratio_SR <- run_pairwise_t_test(
  data = RLP_CC_ratio_SR,
  response = "SR_2024",
  group = "Collection_count_ratio_cluster",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_CC_ratio_SR


pairwise_CC_ratio_SR_plot <- pairwise_CC_ratio_SR %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_CC_ratio_SR <- effectsize::eta_squared(
  anova_CC_ratio_SR$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_CC_ratio_SR


eta2_label_CC_ratio_SR <- paste0(
  "\u03B7² = ",
  round(
    eta2_CC_ratio_SR$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_CC_ratio_SR <- format_anova_label(
  p = anova_CC_ratio_SR$anova_p,
  method = anova_CC_ratio_SR$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_CC_ratio_SR


#######################################
### Y-axis preparation
#######################################

y_interval_CC_ratio_SR <- 10
y_break_max_CC_ratio_SR <- 80
y_max_CC_ratio_SR <- 90

n_label_y_CC_ratio_SR <- 75

significance_y_CC_ratio_SR <- c(
  84,
  92,
  100
)[
  seq_len(
    nrow(pairwise_CC_ratio_SR_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_CC_ratio_SR <- ggplot(
  RLP_CC_ratio_SR,
  aes(
    x = Collection_count_ratio_cluster,
    y = SR_2024
  )
) +
  geom_boxplot(
    fill = "transparent",
    color = "black",
    linewidth = 1.5
  ) +
  stat_summary(
    fun = mean,
    geom = "point",
    shape = 4,
    size = 8,
    color = "black"
  ) +
  add_plot_label(
    label = anova_label_CC_ratio_SR,
    hjust = 1.0,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_CC_ratio_SR,
    hjust = 1.0,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_CC_ratio_SR,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_CC_ratio_SR_plot,
    y_positions = significance_y_CC_ratio_SR,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CC_ratio_SR,
      by = y_interval_CC_ratio_SR
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_CC_ratio_SR
    )
  ) +
  labs(
    x = "Annual collection counts ratio of biowaste to residual waste",
    y = "Biowaste stream separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_CC_ratio_SR


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "RLP",
    "Collection count ratio on biowaste stream separation rate_RLP.png"
  ),
  plot = gg_CC_ratio_SR,
  width = 16,
  height = 9,
  dpi = 300
)


##################################################
### KPI 3b: Biowaste stream separation rate
### matched to SR_approxBW_2024 sample
##################################################

#####################
### Data preparation
#####################

RLP_CC_ratio_SR_matched <- RLP %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(SR_2024),
    !is.na(SR_approxBW_2024),
    !is.na(Collection_count_ratio_cluster)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Collection_count_ratio_cluster,
    Population_2024,
    SR_2024,
    SR_approxBW_2024
  ) %>%
  mutate(
    Collection_count_ratio_cluster = droplevels(
      Collection_count_ratio_cluster
    )
  )

RLP_CC_ratio_SR_matched



#######################################
### Summary
#######################################

RLP_CC_ratio_SR_matched_summary <- RLP_CC_ratio_SR_matched %>%
  summary_statistics(
    summary_var = "SR_2024",
    group_var = "Collection_count_ratio_cluster",
    digits = 2
  )

RLP_CC_ratio_SR_matched_summary


#######################################
### ANOVA
#######################################

anova_CC_ratio_SR_matched <- run_oneway_test(
  data = RLP_CC_ratio_SR_matched,
  response = "SR_2024",
  group = "Collection_count_ratio_cluster"
)

anova_CC_ratio_SR_matched$levene_result
anova_CC_ratio_SR_matched$levene_p
anova_CC_ratio_SR_matched$anova_method
anova_CC_ratio_SR_matched$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_CC_ratio_SR_matched <- run_pairwise_t_test(
  data = RLP_CC_ratio_SR_matched,
  response = "SR_2024",
  group = "Collection_count_ratio_cluster",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_CC_ratio_SR_matched


pairwise_CC_ratio_SR_matched_plot <- pairwise_CC_ratio_SR_matched %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_CC_ratio_SR_matched <- effectsize::eta_squared(
  anova_CC_ratio_SR_matched$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_CC_ratio_SR_matched


eta2_label_CC_ratio_SR_matched <- paste0(
  "η² = ",
  round(
    eta2_CC_ratio_SR_matched$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_CC_ratio_SR_matched <- format_anova_label(
  p = anova_CC_ratio_SR_matched$anova_p,
  method = anova_CC_ratio_SR_matched$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_CC_ratio_SR_matched


#######################################
### Y-axis preparation
#######################################

y_interval_CC_ratio_SR_matched <- 20
y_break_max_CC_ratio_SR_matched <- 100
y_max_CC_ratio_SR_matched <- 132

n_label_y_CC_ratio_SR_matched <- 102

significance_y_CC_ratio_SR_matched <- c(
  110,
  118,
  126
)[
  seq_len(
    nrow(pairwise_CC_ratio_SR_matched_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_CC_ratio_SR_matched <- ggplot(
  RLP_CC_ratio_SR_matched,
  aes(
    x = Collection_count_ratio_cluster,
    y = SR_2024
  )
) +
  geom_boxplot(
    fill = "transparent",
    color = "black",
    linewidth = 1.5
  ) +
  stat_summary(
    fun = mean,
    geom = "point",
    shape = 4,
    size = 8,
    color = "black"
  ) +
  add_plot_label(
    label = anova_label_CC_ratio_SR_matched,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_CC_ratio_SR_matched,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_CC_ratio_SR_matched,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_CC_ratio_SR_matched_plot,
    y_positions = significance_y_CC_ratio_SR_matched,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CC_ratio_SR_matched,
      by = y_interval_CC_ratio_SR_matched
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_CC_ratio_SR_matched
    )
  ) +
  labs(
    x = "Annual collection counts ratio of biowaste to residual waste",
    y = "Biowaste stream separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_CC_ratio_SR_matched


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "RLP",
    "Collection count ratio on biowaste stream separation rate_matched sample_RLP.png"
  ),
  plot = gg_CC_ratio_SR_matched,
  width = 16,
  height = 9,
  dpi = 300
)






##################################################
### KPI 4: Approximated net biowaste separation rate
##################################################

#####################
### Data preparation
#####################

RLP_CC_ratio_SR_approxBW <- RLP %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(SR_approxBW_2024),
    !is.na(Collection_count_ratio_cluster)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Collection_count_ratio_cluster,
    Population_2024,
    SR_approxBW_2024
  ) %>%
  mutate(
    Collection_count_ratio_cluster = droplevels(
      Collection_count_ratio_cluster
    )
  )

RLP_CC_ratio_SR_approxBW


#######################################
### Summary
#######################################

RLP_CC_ratio_SR_approxBW_summary <-
  RLP_CC_ratio_SR_approxBW %>%
  summary_statistics(
    summary_var = "SR_approxBW_2024",
    group_var = "Collection_count_ratio_cluster",
    digits = 2
  )

RLP_CC_ratio_SR_approxBW_summary


#######################################
### ANOVA
#######################################

anova_CC_ratio_SR_approxBW <- run_oneway_test(
  data = RLP_CC_ratio_SR_approxBW,
  response = "SR_approxBW_2024",
  group = "Collection_count_ratio_cluster"
)


# Levene test

anova_CC_ratio_SR_approxBW$levene_result

anova_CC_ratio_SR_approxBW$levene_p


# Selected ANOVA method

anova_CC_ratio_SR_approxBW$anova_method

anova_CC_ratio_SR_approxBW$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_CC_ratio_SR_approxBW <- run_pairwise_t_test(
  data = RLP_CC_ratio_SR_approxBW,
  response = "SR_approxBW_2024",
  group = "Collection_count_ratio_cluster",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_CC_ratio_SR_approxBW


pairwise_CC_ratio_SR_approxBW_plot <-
  pairwise_CC_ratio_SR_approxBW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_CC_ratio_SR_approxBW <-
  effectsize::eta_squared(
    anova_CC_ratio_SR_approxBW$anova_model,
    partial = FALSE,
    ci = 0.95
  )

eta2_CC_ratio_SR_approxBW


eta2_label_CC_ratio_SR_approxBW <- paste0(
  "\u03B7² = ",
  round(
    eta2_CC_ratio_SR_approxBW$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_CC_ratio_SR_approxBW <-
  format_anova_label(
    p = anova_CC_ratio_SR_approxBW$anova_p,
    method = anova_CC_ratio_SR_approxBW$anova_method,
    show_method = FALSE,
    show_significance = FALSE
  )

anova_label_CC_ratio_SR_approxBW


#######################################
### Y-axis preparation
#######################################

y_interval_CC_ratio_SR_approxBW <- 10
y_break_max_CC_ratio_SR_approxBW <- 100
y_max_CC_ratio_SR_approxBW <- 120

n_label_y_CC_ratio_SR_approxBW <- 100

significance_y_CC_ratio_SR_approxBW <- c(
  110,
  118,
  126
)[
  seq_len(
    nrow(pairwise_CC_ratio_SR_approxBW_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_CC_ratio_SR_approxBW <- ggplot(
  RLP_CC_ratio_SR_approxBW,
  aes(
    x = Collection_count_ratio_cluster,
    y = SR_approxBW_2024
  )
) +
  geom_boxplot(
    fill = "transparent",
    color = "black",
    linewidth = 1.5
  ) +
  stat_summary(
    fun = mean,
    geom = "point",
    shape = 4,
    size = 8,
    color = "black"
  ) +
  add_plot_label(
    label = anova_label_CC_ratio_SR_approxBW,
    hjust = 1.0,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_CC_ratio_SR_approxBW,
    hjust = 1.0,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_CC_ratio_SR_approxBW,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_CC_ratio_SR_approxBW_plot,
    y_positions = significance_y_CC_ratio_SR_approxBW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CC_ratio_SR_approxBW,
      by = y_interval_CC_ratio_SR_approxBW
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_CC_ratio_SR_approxBW
    )
  ) +
  labs(
    x = "Annual collection counts ratio of biowaste to residual waste",
    y = "Aprx. net biowaste separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_CC_ratio_SR_approxBW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "RLP",
    "Collection count ratio on approximated net biowaste separation rate_RLP.png"
  ),
  plot = gg_CC_ratio_SR_approxBW,
  width = 16,
  height = 9,
  dpi = 300
)






##################################################
### KPI 5: Unpackaged food waste in residual waste
##################################################

#####################
### Data preparation
#####################

RLP_CC_ratio_FWunpack_RW <- RLP %>%
  filter(
    Waste_Category == "Residual waste",
    !is.na(FWunpack_RW_kg),
    !is.na(Collection_count_ratio_cluster)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Collection_count_ratio_cluster,
    Population_2024,
    FWunpack_RW_kg
  ) %>%
  mutate(
    Collection_count_ratio_cluster = droplevels(
      Collection_count_ratio_cluster
    )
  )

RLP_CC_ratio_FWunpack_RW


#######################################
### Summary
#######################################

RLP_CC_ratio_FWunpack_RW_summary <-
  RLP_CC_ratio_FWunpack_RW %>%
  summary_statistics(
    summary_var = "FWunpack_RW_kg",
    group_var = "Collection_count_ratio_cluster",
    digits = 2
  )

RLP_CC_ratio_FWunpack_RW_summary


#######################################
### ANOVA
#######################################

anova_CC_ratio_FWunpack_RW <- run_oneway_test(
  data = RLP_CC_ratio_FWunpack_RW,
  response = "FWunpack_RW_kg",
  group = "Collection_count_ratio_cluster"
)


# Levene test

anova_CC_ratio_FWunpack_RW$levene_result

anova_CC_ratio_FWunpack_RW$levene_p


# Selected ANOVA method

anova_CC_ratio_FWunpack_RW$anova_method

anova_CC_ratio_FWunpack_RW$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_CC_ratio_FWunpack_RW <- run_pairwise_t_test(
  data = RLP_CC_ratio_FWunpack_RW,
  response = "FWunpack_RW_kg",
  group = "Collection_count_ratio_cluster",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_CC_ratio_FWunpack_RW


pairwise_CC_ratio_FWunpack_RW_plot <-
  pairwise_CC_ratio_FWunpack_RW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_CC_ratio_FWunpack_RW <- effectsize::eta_squared(
  anova_CC_ratio_FWunpack_RW$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_CC_ratio_FWunpack_RW


eta2_label_CC_ratio_FWunpack_RW <- paste0(
  "η² = ",
  round(
    eta2_CC_ratio_FWunpack_RW$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_CC_ratio_FWunpack_RW <- format_anova_label(
  p = anova_CC_ratio_FWunpack_RW$anova_p,
  method = anova_CC_ratio_FWunpack_RW$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_CC_ratio_FWunpack_RW


#######################################
### Y-axis preparation
#######################################

y_interval_CC_ratio_FWunpack_RW <- 10
y_break_max_CC_ratio_FWunpack_RW <- 70
y_max_CC_ratio_FWunpack_RW <- 75

n_label_y_CC_ratio_FWunpack_RW <- 60

significance_y_CC_ratio_FWunpack_RW <- c(
  96,
  102,
  108
)[
  seq_len(
    nrow(pairwise_CC_ratio_FWunpack_RW_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_CC_ratio_FWunpack_RW <- ggplot(
  RLP_CC_ratio_FWunpack_RW,
  aes(
    x = Collection_count_ratio_cluster,
    y = FWunpack_RW_kg
  )
) +
  geom_boxplot(
    fill = "transparent",
    color = "black",
    linewidth = 1.5
  ) +
  stat_summary(
    fun = mean,
    geom = "point",
    shape = 4,
    size = 8,
    color = "black"
  ) +
  add_plot_label(
    label = anova_label_CC_ratio_FWunpack_RW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_CC_ratio_FWunpack_RW,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_CC_ratio_FWunpack_RW,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_CC_ratio_FWunpack_RW_plot,
    y_positions = significance_y_CC_ratio_FWunpack_RW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CC_ratio_FWunpack_RW,
      by = y_interval_CC_ratio_FWunpack_RW
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_CC_ratio_FWunpack_RW
    )
  ) +
  labs(
    x = "Annual collection counts ratio of biowaste to residual waste",
    y = bquote(
      atop(
        "Unpack. food waste in residual waste",
        "[" * kg ~ inh^{-1} ~ a^{-1} * "]"
      )
    )
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_CC_ratio_FWunpack_RW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "RLP",
    "Collection count ratio on unpackaged food waste in residual waste_RLP.png"
  ),
  plot = gg_CC_ratio_FWunpack_RW,
  width = 16,
  height = 9,
  dpi = 300
)





##################################################
### KPI 6: Total food waste in residual waste
##################################################

#####################
### Data preparation
#####################

RLP_CC_ratio_FWtot_RW <- RLP %>%
  filter(
    Waste_Category == "Residual waste",
    !is.na(FWtot_RW_kg),
    !is.na(Collection_count_ratio_cluster)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Collection_count_ratio_cluster,
    Population_2024,
    FWtot_RW_kg
  ) %>%
  mutate(
    Collection_count_ratio_cluster = droplevels(
      Collection_count_ratio_cluster
    )
  )

RLP_CC_ratio_FWtot_RW


#######################################
### Summary
#######################################

RLP_CC_ratio_FWtot_RW_summary <-
  RLP_CC_ratio_FWtot_RW %>%
  summary_statistics(
    summary_var = "FWtot_RW_kg",
    group_var = "Collection_count_ratio_cluster",
    digits = 2
  )

RLP_CC_ratio_FWtot_RW_summary


#######################################
### ANOVA
#######################################

anova_CC_ratio_FWtot_RW <- run_oneway_test(
  data = RLP_CC_ratio_FWtot_RW,
  response = "FWtot_RW_kg",
  group = "Collection_count_ratio_cluster"
)


# Levene test

anova_CC_ratio_FWtot_RW$levene_result

anova_CC_ratio_FWtot_RW$levene_p


# Selected ANOVA method

anova_CC_ratio_FWtot_RW$anova_method

anova_CC_ratio_FWtot_RW$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_CC_ratio_FWtot_RW <- run_pairwise_t_test(
  data = RLP_CC_ratio_FWtot_RW,
  response = "FWtot_RW_kg",
  group = "Collection_count_ratio_cluster",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_CC_ratio_FWtot_RW


pairwise_CC_ratio_FWtot_RW_plot <-
  pairwise_CC_ratio_FWtot_RW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_CC_ratio_FWtot_RW <- effectsize::eta_squared(
  anova_CC_ratio_FWtot_RW$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_CC_ratio_FWtot_RW


eta2_label_CC_ratio_FWtot_RW <- paste0(
  "η² = ",
  round(
    eta2_CC_ratio_FWtot_RW$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_CC_ratio_FWtot_RW <- format_anova_label(
  p = anova_CC_ratio_FWtot_RW$anova_p,
  method = anova_CC_ratio_FWtot_RW$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_CC_ratio_FWtot_RW


#######################################
### Y-axis preparation
#######################################

y_interval_CC_ratio_FWtot_RW <- 10
y_break_max_CC_ratio_FWtot_RW <- 90
y_max_CC_ratio_FWtot_RW <- 92

n_label_y_CC_ratio_FWtot_RW <- 75

significance_y_CC_ratio_FWtot_RW <- c(
  96,
  102,
  108
)[
  seq_len(
    nrow(pairwise_CC_ratio_FWtot_RW_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_CC_ratio_FWtot_RW <- ggplot(
  RLP_CC_ratio_FWtot_RW,
  aes(
    x = Collection_count_ratio_cluster,
    y = FWtot_RW_kg
  )
) +
  geom_boxplot(
    fill = "transparent",
    color = "black",
    linewidth = 1.5
  ) +
  stat_summary(
    fun = mean,
    geom = "point",
    shape = 4,
    size = 8,
    color = "black"
  ) +
  add_plot_label(
    label = anova_label_CC_ratio_FWtot_RW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_CC_ratio_FWtot_RW,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_CC_ratio_FWtot_RW,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_CC_ratio_FWtot_RW_plot,
    y_positions = significance_y_CC_ratio_FWtot_RW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CC_ratio_FWtot_RW,
      by = y_interval_CC_ratio_FWtot_RW
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_CC_ratio_FWtot_RW
    )
  ) +
  labs(
    x = "Annual collection counts ratio of biowaste to residual waste",
    y = bquote(
      atop(
        "Food waste in residual waste stream",
        "[" * kg ~ inh^{-1} ~ a^{-1} * "]"
      )
    )
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_CC_ratio_FWtot_RW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "RLP",
    "Collection count ratio on total food waste in residual waste_RLP.png"
  ),
  plot = gg_CC_ratio_FWtot_RW,
  width = 16,
  height = 9,
  dpi = 300
)

