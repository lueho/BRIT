source("R/bootstrap.R")

###############
### Packages
###############

library(ggpubr)
library(ggplot2)
library(grid)
library(tidyverse)
library(rstatix)
library(car)
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
### Font registration
###############################

if (.Platform$OS.type == "windows") {
  windowsFonts(
    Calibri = windowsFont("Calibri")
  )
}


################
### Raw data
################

BOLZANO <- read.csv(
  file = brit_path(
    "data",
    "raw",
    "Alto Adige",
    "BRIT_Italien_Südtirol_2024_SW.csv"
  ),
  na.strings = "#NV",
  header = TRUE,
  sep = ";",
  dec = ".",
  fileEncoding = "Windows-1252"
)


# KPI 7 and KPI 8:
# Residual waste composition
BOLZANO_RWcomp <- read.csv(
  file = brit_path(
    "data",
    "raw",
    "Alto Adige",
    "BRIT_Italien_Südtirol_2024_Restmuellzusammensetzung.csv"
  ),
  na.strings = "#NV",
  header = TRUE,
  sep = ";",
  dec = ".",
  fileEncoding = "Windows-1252"
)


#######################################
### Common category vectors
#######################################

biowaste_categories <- c(
  "Biowaste",
  "Food waste"
)

dtd_collection_systems <- c(
  "Door to door",
  "Mixed door to door and bring point",
  "Mixed door to door and recycling centre"
)


################################################################################
### Descriptive statistics
################################################################################

#######################################
### KPIs
#######################################


##############################
### Biowaste quantities
##############################

BOLZANO_BW_summary <- BOLZANO %>%
  filter(
    !is.na(Collection_System),
    Collection_System != "",
    Waste_Category %in% c("Food waste", "Biowaste")
  ) %>%
  distinct(
    NUTS_LAU,
    Specific_Waste_2024_kg
  ) %>%
  summary_statistics(
    summary_var = "Specific_Waste_2024_kg"
  )

BOLZANO_BW_summary


##############################
### Total organics quantities
##############################

BOLZANO_total_organics <- BOLZANO %>%
  mutate(
    Waste_Category = trimws(Waste_Category),
    Collection_System = trimws(Collection_System)
  ) %>%
  filter(
    Waste_Category %in% c(
      "Biowaste",
      "Food waste",
      "Green waste"
    )
  ) %>%
  group_by(
    NUTS_LAU
  ) %>%
  filter(
    any(
      !is.na(Collection_System) &
        Collection_System != "" &
        Collection_System != "No separate collection"
    )
  ) %>%
  summarise(
    Target_biowaste_2024_kg = sum(
      Specific_Waste_2024_kg[
        Waste_Category %in% c(
          "Biowaste",
          "Food waste"
        ) &
          !is.na(Collection_System) &
          Collection_System != "" &
          Collection_System != "No separate collection"
      ],
      na.rm = TRUE
    ),
    Green_waste_2024_kg = sum(
      Specific_Waste_2024_kg[
        Waste_Category == "Green waste" &
          !is.na(Collection_System) &
          Collection_System != "" &
          Collection_System != "No separate collection"
      ],
      na.rm = TRUE
    ),
    .groups = "drop"
  ) %>%
  mutate(
    Total_organics_2024_kg =
      Target_biowaste_2024_kg +
      Green_waste_2024_kg
  )

BOLZANO_total_organics

BOLZANO_total_organics_summary <- BOLZANO_total_organics %>%
  summary_statistics(
    summary_var = "Total_organics_2024_kg",
    digits = 1
  )

BOLZANO_total_organics_summary



##############################
### Residual waste quantities
##############################

BOLZANO_RW_summary <- BOLZANO %>%
  filter(
    !is.na(Collection_System),
    Collection_System != "",
    Waste_Category == "Residual waste"
  ) %>%
  distinct(
    NUTS_LAU,
    Specific_Waste_2024_kg
  ) %>%
  summary_statistics(
    summary_var = "Specific_Waste_2024_kg"
  )

BOLZANO_RW_summary



#################################
### Biowaste in residual waste
#################################

BOLZANO_BW_RW_summary <- BOLZANO_RWcomp %>%
  summary_statistics(
    summary_var = "BW_RW_kg"
  )

BOLZANO_BW_RW_summary



##############################
### Separation rate
##############################

BOLZANO_SR_summary <- BOLZANO %>%
  filter(
    !is.na(Collection_System),
    Collection_System != "",
    Waste_Category %in% biowaste_categories
  ) %>%
  distinct(
    NUTS_LAU,
    SR_2024
  ) %>%
  summary_statistics(
    summary_var = "SR_2024"
  )

BOLZANO_SR_summary



#######################################
### Municipalities and population
### above/below 50% separation rate
#######################################

BOLZANO_SR_50_distribution <- BOLZANO %>%
  filter(
    !is.na(Collection_System),
    Collection_System != "",
    Waste_Category %in% biowaste_categories,
    !is.na(SR_2024),
    !is.na(Population_2024)
  ) %>%
  distinct(
    NUTS_LAU,
    Population_2024,
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
    sort_by = "category"
  )

BOLZANO_SR_50_distribution



##############################
### approximated net Separation rate
##############################

#################################
### Biowaste in residual waste
#################################

BOLZANO_approxBW_SR_summary <- BOLZANO_RWcomp %>%
  mutate(
    SR_BWapprox = SR_BWapprox * 100
  ) %>%
  summary_statistics(
    summary_var = "SR_BWapprox",
    digits = 1
  )

BOLZANO_approxBW_SR_summary





#######################################
### Influencing Factors
#######################################

##############################
### IF: Collection mode
##############################

BOLZANO_sepcol <- BOLZANO %>%
  filter(
    Waste_Category %in% biowaste_categories,
    !is.na(Collection_System),
    Collection_System != ""
  ) %>%
  summarise_population_distribution(
    category_var = "Collection_System",
    sort_by = "entries_desc"
  )

BOLZANO_sepcol


##############################
### IF: Target waste category
##############################

BOLZANO_target <- BOLZANO %>%
  filter(
    Waste_Category %in% biowaste_categories,
    !is.na(Collection_System),
    Collection_System != "",
    Collection_System != "No separate collection"
  ) %>%
  summarise_population_distribution(
    category_var = "Waste_Category",
    sort_by = "entries_desc"
  )

BOLZANO_target


##############################
### IF: Minimum bin size
##############################

#######################################
### General summary
#######################################

BOLZANO_binsize <- BOLZANO %>%
  filter(
    Collection_System %in% dtd_collection_systems,
    Waste_Category %in% biowaste_categories
  ) %>%
  distinct(
    NUTS_LAU,
    Minimum_bin_size_L
  ) %>%
  summary_statistics(
    summary_var = "Minimum_bin_size_L"
  )

BOLZANO_binsize


#######################################
### Comparison by target category
#######################################

BOLZANO_binsize_target <- BOLZANO %>%
  filter(
    Collection_System %in% dtd_collection_systems,
    Waste_Category %in% biowaste_categories
  ) %>%
  distinct(
    NUTS_LAU,
    Waste_Category,
    Minimum_bin_size_L
  ) %>%
  summary_statistics(
    summary_var = "Minimum_bin_size_L",
    group_var = "Waste_Category"
  )

BOLZANO_binsize_target


#######################################
### Bin-size categories
#######################################

BOLZANO_minimum_bin_size <- BOLZANO %>%
  filter(
    Collection_System %in% dtd_collection_systems,
    Waste_Category == "Biowaste",
    !is.na(Minimum_bin_size_L)
  ) %>%
  distinct(
    NUTS_LAU,
    Population_2024,
    Minimum_bin_size_L
  ) %>%
  mutate(
    Minimum_bin_size_category = case_when(
      Minimum_bin_size_L <= 26.5 ~ "≤ 26.5 L",
      Minimum_bin_size_L <= 80   ~ "> 26.5–80 L",
      Minimum_bin_size_L > 80    ~ "> 80 L"
    ),
    Minimum_bin_size_category = factor(
      Minimum_bin_size_category,
      levels = c(
        "≤ 26.5 L",
        "> 26.5–80 L",
        "> 80 L"
      )
    )
  )


#######################################
### Population distribution
#######################################

BOLZANO_minimum_bin_size_distribution <-
  BOLZANO_minimum_bin_size %>%
  summarise_population_distribution(
    category_var = "Minimum_bin_size_category",
    sort_by = "category"
  )

BOLZANO_minimum_bin_size_distribution


############################################################################
### Statistical assessment KPI vs IF - Target waste category
############################################################################

###############################################
### KPI 1: Biowaste/Food waste quantities
###############################################

#####################
### Data preparation
#####################

Bolzano_target_BW <- BOLZANO %>%
  mutate(
    Collection_System = trimws(Collection_System),
    Waste_Category = factor(
      trimws(Waste_Category),
      levels = c(
        "Biowaste",
        "Food waste"
      ),
      labels = c(
        "Commingled biowaste",
        "Food waste"
      )
    )
  ) %>%
  filter(
    !is.na(Waste_Category),
    !is.na(Specific_Waste_2024_kg),
    !is.na(Collection_System),
    Collection_System != "No separate collection"
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Waste_Category,
    Specific_Waste_2024_kg
  )

Bolzano_target_BW


#######################################
### Summary
#######################################

Bolzano_BW_target_summary <- summary_statistics(
  data = Bolzano_target_BW,
  summary_var = "Specific_Waste_2024_kg",
  group_var = "Waste_Category",
  digits = 1
)

Bolzano_BW_target_summary


#######################################
## Pairwise t-test
#######################################

# Complete, unfiltered test results
ttest_target_BW <- run_pairwise_t_test(
  data = Bolzano_target_BW,
  response = "Specific_Waste_2024_kg",
  group = "Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_target_BW


# Significant results used only for plotting
ttest_target_BW_plot <- ttest_target_BW %>%
  filter(
    p.adj.signif != "ns"
  )

ttest_target_BW_plot


#######################################
## Effect size: Cohen's d
#######################################

d_target_BW <- effectsize::cohens_d(
  Specific_Waste_2024_kg ~ Waste_Category,
  data = Bolzano_target_BW,
  pooled_sd = FALSE
)

d_target_BW


d_label_target_BW <- d_target_BW %>%
  transmute(
    label = paste0(
      "Cohen's d = ",
      round(Cohens_d, 1)
    )
  ) %>%
  pull(label)

d_label_target_BW


#######################################
## Y-axis preparation
#######################################

y_axis_BW <- prepare_y_axis_quantity(
  data = Bolzano_target_BW,
  value_var = "Specific_Waste_2024_kg",
  interval = 50,                              # change
  n_significance = nrow(ttest_target_BW_plot)
)

y_axis_BW



#######################################
## Y-axis preparation: manuelle Einstellung
#######################################

y_interval_BW <- 50
y_break_max_BW <- 340

y_max_BW <- y_break_max_BW +
  y_interval_BW * 0.10

y_n_BW <- y_break_max_BW * 0.84
y_significance_BW <- y_break_max_BW * 0.94



#######################################
## Boxplot: Biowaste/Food waste
## quantities by target category
#######################################

gg_target_BW <- ggplot(
  Bolzano_target_BW,
  aes(
    x = Waste_Category,
    y = Specific_Waste_2024_kg
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
    color = "black",
    position = position_dodge(width = 0.75)
  ) +
  add_plot_label(
    label = d_label_target_BW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_n_labels(
    y_position = y_n_BW,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = ttest_target_BW_plot,
    y_positions = y_significance_BW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_BW,
      by = y_interval_BW
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_max_BW)
  ) +
  labs(
    x = "Target biowaste category",
    y = bquote("Biowaste stream [" *kg ~ inh^{-1} ~ a^{-1} *"]")
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_target_BW
  





#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Target biowaste category on biowaste quantities_Bolzano.png"
  ),
  plot = gg_target_BW,
  width = 16,
  height = 9,
  dpi = 300
)

### There are a few extreme outliers that are not shown on the figure!




###############################################
### KPI 2: Residual waste quantities
### (incl. no separate collection)
###############################################

#####################
### Data preparation
#####################

# Target category per collection area
Bolzano_target_category_lookup <- BOLZANO %>%
  mutate(
    Waste_Category = trimws(Waste_Category),
    Collection_System = trimws(Collection_System),
    Target_Waste_Category = case_when(
      Collection_System == "No separate collection" ~
        "No separate collection",
      Waste_Category == "Biowaste" ~
        "Commingled biowaste",
      Waste_Category == "Food waste" ~
        "Food waste",
      TRUE ~ NA_character_
    ),
    Target_Waste_Category = factor(
      Target_Waste_Category,
      levels = c(
        "Commingled biowaste",
        "Food waste",
        "No separate collection"
      )
    )
  ) %>%
  filter(
    Waste_Category %in% c(
      "Biowaste",
      "Food waste"
    ),
    !is.na(Target_Waste_Category)
  ) %>%
  distinct(
    NUTS_LAU,
    Target_Waste_Category
  )


# Link target category to residual waste
Bolzano_target_RW <- BOLZANO %>%
  mutate(
    Waste_Category = trimws(Waste_Category)
  ) %>%
  filter(
    Waste_Category == "Residual waste",
    !is.na(Specific_Waste_2024_kg)
  ) %>%
  left_join(
    Bolzano_target_category_lookup,
    by = "NUTS_LAU"
  ) %>%
  filter(
    !is.na(Target_Waste_Category)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Target_Waste_Category,
    Specific_Waste_2024_kg
  )

Bolzano_target_RW


#######################################
### Summary
#######################################

Bolzano_RW_BWtarget_summary <- summary_statistics(
  data = Bolzano_target_RW,
  summary_var = "Specific_Waste_2024_kg",
  group_var = "Target_Waste_Category"
)

Bolzano_RW_BWtarget_summary


#######################################
## ANOVA assumption check and testing
#######################################

Bolzano_RW_test <- run_oneway_test(
  data = Bolzano_target_RW,
  response = "Specific_Waste_2024_kg",
  group = "Target_Waste_Category"
)


# Extract individual results
levene_result_RW <- Bolzano_RW_test$levene_result
levene_p_RW <- Bolzano_RW_test$levene_p

anova_model_RW <- Bolzano_RW_test$anova_model
anova_result_RW <- Bolzano_RW_test$anova_result
anova_method_RW <- Bolzano_RW_test$anova_method
anova_p_RW <- Bolzano_RW_test$anova_p

levene_result_RW
anova_method_RW
anova_result_RW


# ANOVA label for boxplot
anova_label_RW <- format_anova_label(
  p = anova_p_RW
)

anova_label_RW


#######################################
## Pairwise significance testing
#######################################

# Complete, unfiltered test results
pairwise_t_results_RW <- run_pairwise_t_test(
  data = Bolzano_target_RW,
  response = "Specific_Waste_2024_kg",
  group = "Target_Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_t_results_RW


# Significant results used only for plotting
pairwise_t_results_RW_plot <- pairwise_t_results_RW %>%
  filter(
    p.adj.signif != "ns"
  )

pairwise_t_results_RW_plot


#######################################
## Effect size: Eta squared
#######################################

eta2_target_RW <- effectsize::eta_squared(
  anova_model_RW,
  partial = FALSE
)

eta2_target_RW


# Label for boxplot
eta2_label_target_RW <- eta2_target_RW %>%
  transmute(
    label = paste0(
      "\u03b7\u00b2 = ",
      round(Eta2, 2)
    )
  ) %>%
  pull(label)

eta2_label_target_RW


#######################################
## Y-axis preparation
#######################################

y_axis_RW <- prepare_y_axis_quantity_compact_significance(
  data = Bolzano_target_RW,
  value_var = "Specific_Waste_2024_kg",
  interval = 50,
  test_results = pairwise_t_results_RW_plot,
  group_levels = levels(Bolzano_target_RW$Target_Waste_Category)
)

y_axis_RW


#######################################
## Boxplot: Residual waste quantities
## by target waste category
#######################################

gg_target_RW <- ggplot(
  Bolzano_target_RW,
  aes(
    x = Target_Waste_Category,
    y = Specific_Waste_2024_kg
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
    color = "black",
    position = position_dodge(width = 0.75)
  ) +
  add_n_labels(
    y_position = y_axis_RW$n_label_y,
    size = 10,
    vjust = 0
  ) +
  add_plot_label(
    label = anova_label_RW,
    hjust = 1,
    vjust = 1,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_target_RW,
    hjust = 1,
    vjust = 3,
    size = 10
  ) +
  add_significance_labels(
    test_results = pairwise_t_results_RW_plot,
    y_positions = y_axis_RW$significance_y_positions,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_axis_RW$break_max,
      by = y_axis_RW$interval
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_axis_RW$y_max)
  ) +
  labs(
    x = "Target biowaste category",
    y = bquote("Residual waste stream [" *kg ~ inh^{-1} ~ a^{-1} *"]")
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_target_RW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Target biowaste category on residual waste quantities_Bolzano.png"
  ),
  plot = gg_target_RW,
  width = 16,
  height = 9,
  dpi = 300
)



###############################################
### KPI 3: Separation rate
###############################################

#####################
### Data preparation
#####################

Bolzano_target_SR <- BOLZANO %>%
  mutate(
    Collection_System = trimws(Collection_System),
    Waste_Category = factor(
      trimws(Waste_Category),
      levels = c(
        "Biowaste",
        "Food waste"
      ),
      labels = c(
        "Commingled biowaste",
        "Food waste"
      )
    )
  ) %>%
  filter(
    !is.na(Waste_Category),
    !is.na(SR_2024),
    !is.na(Collection_System),
    Collection_System != "No separate collection"
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Waste_Category,
    SR_2024
  )

Bolzano_target_SR


#######################################
### Summary
#######################################

Bolzano_SR_target_summary <- summary_statistics(
  data = Bolzano_target_SR,
  summary_var = "SR_2024",
  group_var = "Waste_Category",
  digits = 1
)

Bolzano_SR_target_summary



#######################################
## Pairwise t-test
#######################################

# Complete, unfiltered test results
ttest_target_SR <- run_pairwise_t_test(
  data = Bolzano_target_SR,
  response = "SR_2024",
  group = "Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_target_SR


# Significant results used only for plotting
ttest_target_SR_plot <- ttest_target_SR %>%
  filter(
    p.adj.signif != "ns"
  )

ttest_target_SR_plot


#######################################
## Effect size: Cohen's d
#######################################

d_target_SR <- effectsize::cohens_d(
  SR_2024 ~ Waste_Category,
  data = Bolzano_target_SR,
  pooled_sd = FALSE
)

d_target_SR


# Label for boxplot
d_label_target_SR <- d_target_SR %>%
  transmute(
    label = paste0(
      "Cohen's d = ",
      round(Cohens_d, 1)
    )
  ) %>%
  pull(label)

d_label_target_SR


#######################################
## Y-axis preparation
#######################################

y_axis_SR <- prepare_y_axis_percent(
  data = Bolzano_target_SR,
  value_var = "SR_2024",
  interval = 10,
  max_break = 100,
  test_results = ttest_target_SR_plot,
  group_levels = levels(
    Bolzano_target_SR$Waste_Category
  )
)

y_axis_SR


#######################################
## Boxplot: Separation rate
## by target waste category
#######################################

gg_target_SR <- ggplot(
  Bolzano_target_SR,
  aes(
    x = Waste_Category,
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
    color = "black",
    position = position_dodge(width = 0.75)
  ) +
  add_n_labels(
    y_position = y_axis_SR$n_label_y,
    size = 10,
    vjust = 0
  ) +
  add_plot_label(
    label = d_label_target_SR,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_significance_labels(
    test_results = ttest_target_SR_plot,
    y_positions = y_axis_SR$significance_y_positions,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_axis_SR$break_max,
      by = y_axis_SR$interval
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_axis_SR$y_max
    )
  ) +
  labs(
    x = "Target biowaste category",
    y = "Biowaste stream separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_target_SR


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Target biowaste category on separation rate_Bolzano.png"
  ),
  plot = gg_target_SR,
  width = 16,
  height = 9,
  dpi = 300
)




###############################################
### KPI 2: Residual waste quantities
### Excluding no separate collection
###############################################

#####################
### Data preparation
#####################

# Target category per collection area
Bolzano_target_category_lookup <- BOLZANO %>%
  mutate(
    Waste_Category = trimws(Waste_Category),
    Collection_System = trimws(Collection_System)
  ) %>%
  filter(
    Waste_Category %in% c(
      "Biowaste",
      "Food waste"
    ),
    !is.na(Collection_System),
    Collection_System != "No separate collection"
  ) %>%
  transmute(
    NUTS_LAU,
    Target_Waste_Category = factor(
      Waste_Category,
      levels = c(
        "Biowaste",
        "Food waste"
      ),
      labels = c(
        "Commingled biowaste",
        "Food waste"
      )
    )
  ) %>%
  distinct(
    NUTS_LAU,
    Target_Waste_Category
  )


# Link target category to residual waste
Bolzano_target_RW <- BOLZANO %>%
  mutate(
    Waste_Category = trimws(Waste_Category)
  ) %>%
  filter(
    Waste_Category == "Residual waste",
    !is.na(Specific_Waste_2024_kg)
  ) %>%
  left_join(
    Bolzano_target_category_lookup,
    by = "NUTS_LAU"
  ) %>%
  filter(
    !is.na(Target_Waste_Category)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Target_Waste_Category,
    Specific_Waste_2024_kg
  )

Bolzano_target_RW


#######################################
### Summary
#######################################

Bolzano_RW_BWtarget_summary <- summary_statistics(
  data = Bolzano_target_RW,
  summary_var = "Specific_Waste_2024_kg",
  group_var = "Target_Waste_Category",
  digits = 1
)

Bolzano_RW_BWtarget_summary


#######################################
## Pairwise t-test
#######################################

# Complete, unfiltered test result
ttest_target_RW <- run_pairwise_t_test(
  data = Bolzano_target_RW,
  response = "Specific_Waste_2024_kg",
  group = "Target_Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_target_RW


# Significant result used only for plotting
ttest_target_RW_plot <- ttest_target_RW %>%
  filter(
    p.adj.signif != "ns"
  )

ttest_target_RW_plot


#######################################
## Effect size: Cohen's d
#######################################

d_target_RW <- effectsize::cohens_d(
  Specific_Waste_2024_kg ~ Target_Waste_Category,
  data = Bolzano_target_RW,
  pooled_sd = FALSE
)

d_target_RW


# Label for boxplot
d_label_target_RW <- d_target_RW %>%
  transmute(
    label = paste0(
      "Cohen's d = ",
      round(Cohens_d, 1)
    )
  ) %>%
  pull(label)

d_label_target_RW


#######################################
## Y-axis preparation
#######################################

y_interval_RW <- 50
y_break_max_RW <- 350

# Small margin above the highest labelled break
y_max_RW <- y_break_max_RW +
  y_interval_RW * 0.10

# Manual positions within the displayed range
y_n_RW <- y_break_max_RW * 0.84
y_significance_RW <- y_break_max_RW * 0.94


#######################################
## Boxplot: Residual waste quantities
## by target waste category
#######################################

gg_target_RW <- ggplot(
  Bolzano_target_RW,
  aes(
    x = Target_Waste_Category,
    y = Specific_Waste_2024_kg
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
    color = "black",
    position = position_dodge(width = 0.75)
  ) +
  add_n_labels(
    y_position = y_n_RW,
    size = 10,
    vjust = 0
  ) +
  add_plot_label(
    label = d_label_target_RW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_significance_labels(
    test_results = ttest_target_RW_plot,
    y_positions = y_significance_RW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_RW,
      by = y_interval_RW
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_RW
    )
  ) +
  labs(
    x = "Target biowaste category",
    y = bquote(
      "Residual waste stream [" *
        kg ~ inh^{-1} ~ a^{-1} *
        "]"
    )
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_target_RW


####################
### Save
####################


ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Target biowaste category on residual waste quantities without no separate collection_Bolzano.png"
  ),
  plot = gg_target_RW,
  width = 16,
  height = 9,
  dpi = 300
)



###############################################
### KPI 4: Green waste quantities
###############################################

### achtung es muss erst KPI2 lookup "ohne no sep col" ausgeführt werden!

#####################
### Data preparation
#####################

Bolzano_target_GW <- BOLZANO %>%
  mutate(
    Waste_Category = trimws(Waste_Category)
  ) %>%
  filter(
    Waste_Category == "Green waste",
    !is.na(Specific_Waste_2024_kg)
  ) %>%
  left_join(
    Bolzano_target_category_lookup,
    by = "NUTS_LAU"
  ) %>%
  filter(
    !is.na(Target_Waste_Category)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Target_Waste_Category,
    Specific_Waste_2024_kg
  )

Bolzano_target_GW


#######################################
### Summary
#######################################

Bolzano_GW_target_summary <- summary_statistics(
  data = Bolzano_target_GW,
  summary_var = "Specific_Waste_2024_kg",
  group_var = "Target_Waste_Category"
)

Bolzano_GW_target_summary



#######################################
## Pairwise t-test
#######################################

# Complete, unfiltered test result
ttest_target_GW <- run_pairwise_t_test(
  data = Bolzano_target_GW,
  response = "Specific_Waste_2024_kg",
  group = "Target_Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_target_GW


# Significant result used only for plotting
ttest_target_GW_plot <- ttest_target_GW %>%
  filter(
    p.adj.signif != "ns"
  )

ttest_target_GW_plot


#######################################
## Effect size: Cohen's d
#######################################

d_target_GW <- effectsize::cohens_d(
  Specific_Waste_2024_kg ~ Target_Waste_Category,
  data = Bolzano_target_GW
)

d_target_GW


# Label for boxplot
d_label_target_GW <- d_target_GW %>%
  transmute(
    label = paste0(
      "Cohen's d = ",
      round(Cohens_d, 1)
    )
  ) %>%
  pull(label)

d_label_target_GW




#######################################
## Y-axis preparation
#######################################

y_axis_GW <- prepare_y_axis_quantity(
  data = Bolzano_target_GW,
  value_var = "Specific_Waste_2024_kg",
  interval = 50,
  n_significance = nrow(
    ttest_target_GW_plot
  )
)

y_axis_GW



#######################################
## Boxplot: Green waste quantities
## by target waste category
#######################################

gg_target_GW <- ggplot(
  Bolzano_target_GW,
  aes(
    x = Target_Waste_Category,
    y = Specific_Waste_2024_kg
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
    color = "black",
    position = position_dodge(width = 0.75)
  ) +
  add_n_labels(
    y_position = y_axis_GW$n_label_y,
    size = 10,
    vjust = 0
  ) +
  add_plot_label(
    label = d_label_target_GW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_significance_labels(
    test_results = ttest_target_GW_plot,
    y_positions = y_axis_GW$significance_y_positions,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_axis_GW$break_max,
      by = y_axis_GW$interval
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_axis_GW$y_max
    )
  ) +
  labs(
    x = "Target biowaste category",
    y = bquote(
      "Green waste [" *
        kg ~ inh^{-1} ~ a^{-1} *
        "]"
    )
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_target_GW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Target biowaste category on green waste quantities_Bolzano.png"
  ),
  plot = gg_target_GW,
  width = 16,
  height = 9,
  dpi = 300
)





###############################################
### KPI 5: Total organic waste quantities
###############################################

#####################
### Data preparation
#####################

Bolzano_target_total_organics <- BOLZANO %>%
  mutate(
    Waste_Category = trimws(Waste_Category)
  ) %>%
  filter(
    Waste_Category %in% c(
      "Biowaste",
      "Food waste",
      "Green waste"
    ),
    !is.na(Specific_Waste_2024_kg)
  ) %>%
  left_join(
    Bolzano_target_category_lookup,
    by = "NUTS_LAU"
  ) %>%
  filter(
    !is.na(Target_Waste_Category),
    Waste_Category == "Green waste" |
      (
        Target_Waste_Category == "Commingled biowaste" &
          Waste_Category == "Biowaste"
      ) |
      (
        Target_Waste_Category == "Food waste" &
          Waste_Category == "Food waste"
      )
  ) %>%
  mutate(
    Organics_stream = if_else(
      Waste_Category == "Green waste",
      "Green_waste",
      "Target_biowaste"
    )
  ) %>%
  group_by(
    NUTS_LAU,
    Catchment,
    Target_Waste_Category,
    Organics_stream
  ) %>%
  summarise(
    Specific_Waste_2024_kg = sum(
      Specific_Waste_2024_kg,
      na.rm = TRUE
    ),
    .groups = "drop"
  ) %>%
  pivot_wider(
    names_from = Organics_stream,
    values_from = Specific_Waste_2024_kg
  ) %>%
  mutate(
    Total_organics_2024_kg =
      Target_biowaste + Green_waste
  ) %>%
  filter(
    !is.na(Total_organics_2024_kg)
  )

Bolzano_target_total_organics


#######################################
### Summary
#######################################

Bolzano_total_organics_target_summary <- summary_statistics(
  data = Bolzano_target_total_organics,
  summary_var = "Total_organics_2024_kg",
  group_var = "Target_Waste_Category"
)

Bolzano_total_organics_target_summary




#######################################
## Pairwise t-test
#######################################

# Complete, unfiltered test result
ttest_target_TOS <- run_pairwise_t_test(
  data = Bolzano_target_total_organics,
  response = "Total_organics_2024_kg",
  group = "Target_Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_target_TOS


# Significant result used only for plotting
ttest_target_TOS_plot <- ttest_target_TOS %>%
  filter(
    p.adj.signif != "ns"
  )

ttest_target_TOS_plot


#######################################
## Effect size: Cohen's d
#######################################

d_target_TOS <- effectsize::cohens_d(
  Total_organics_2024_kg ~ Target_Waste_Category,
  data = Bolzano_target_total_organics
)

d_target_TOS


# Label for boxplot
d_label_target_TOS <- d_target_TOS %>%
  transmute(
    label = paste0(
      "Cohen's d = ",
      round(Cohens_d, 1)
    )
  ) %>%
  pull(label)

d_label_target_TOS


#######################################
## Y-axis preparation
#######################################

y_interval_TOS <- 50                                                             #change

y_break_max_TOS <- ceiling(
  max(
    Bolzano_target_total_organics$Total_organics_2024_kg,
    na.rm = TRUE
  ) * 0.6 / y_interval_TOS                                                      #change standard = 1.25
) * y_interval_TOS

y_max_TOS <- y_break_max_TOS +
  y_interval_TOS * 0.10     




#######################################
## Boxplot: TOS quantities
## by target waste category
#######################################

gg_target_TOS <- ggplot(
  Bolzano_target_total_organics,
  aes(
    x = Target_Waste_Category,
    y = Total_organics_2024_kg
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
    color = "black",
    position = position_dodge(width = 0.75)
  ) +
  add_plot_label(
    label = d_label_target_TOS,
    hjust = 1.0,
    vjust = 1.2,
    size = 10
  ) +
  add_n_labels(
    y_position = y_max_TOS * 0.84,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = ttest_target_TOS_plot,
    y_positions = y_max_TOS * 0.92,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_TOS,
      by = y_interval_TOS
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_max_TOS)
  ) +
  labs(
    x = "Target biowaste category",
    y = bquote("Total organics stream [" *kg ~ inh^{-1} ~ a^{-1} *"]")
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_target_TOS


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Target biowaste category on total organics quantities_Bolzano.png"
  ),
  plot = gg_target_TOS,
  width = 16,
  height = 9,
  dpi = 300
)




###############################################
### KPI 6: Total organics separation rate
###############################################

#####################
### Data preparation
#####################

Bolzano_target_TOS_SR <- Bolzano_target_total_organics %>%
  inner_join(
    Bolzano_target_RW %>%
      select(
        NUTS_LAU,
        Target_Waste_Category,
        Residual_waste_2024_kg =
          Specific_Waste_2024_kg
      ),
    by = c(
      "NUTS_LAU",
      "Target_Waste_Category"
    )
  ) %>%
  filter(
    Total_organics_2024_kg +
      Residual_waste_2024_kg > 0
  ) %>%
  mutate(
    TOS_SR_2024 =
      Total_organics_2024_kg /
      (
        Total_organics_2024_kg +
          Residual_waste_2024_kg
      ) *
      100
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Target_Waste_Category,
    Total_organics_2024_kg,
    Residual_waste_2024_kg,
    TOS_SR_2024
  )

Bolzano_target_TOS_SR


#######################################
### Summary
#######################################

Bolzano_TOS_SR_target_summary <- summary_statistics(
  data = Bolzano_target_TOS_SR,
  summary_var = "TOS_SR_2024",
  group_var = "Target_Waste_Category"
)

Bolzano_TOS_SR_target_summary



#######################################
## Pairwise t-test
#######################################

# Complete, unfiltered test result
ttest_target_TOS_SR <- run_pairwise_t_test(
  data = Bolzano_target_TOS_SR,
  response = "TOS_SR_2024",
  group = "Target_Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_target_TOS_SR


# Significant result used only for plotting
ttest_target_TOS_SR_plot <- ttest_target_TOS_SR %>%
  filter(
    p.adj.signif != "ns"
  )

ttest_target_TOS_SR_plot


#######################################
## Effect size: Cohen's d
#######################################

d_target_TOS_SR <- effectsize::cohens_d(
  TOS_SR_2024 ~ Target_Waste_Category,
  data = Bolzano_target_TOS_SR
)

d_target_TOS_SR


# Label for boxplot
d_label_target_TOS_SR <- d_target_TOS_SR %>%
  transmute(
    label = paste0(
      "Cohen's d = ",
      round(Cohens_d, 1)
    )
  ) %>%
  pull(label)

d_label_target_TOS_SR



#######################################
## Y-axis preparation
#######################################

y_axis_TOS_SR <- prepare_y_axis_percent(
  data = Bolzano_target_TOS_SR,
  value_var = "TOS_SR_2024",
  interval = 10,
  max_break = 100,
  test_results = ttest_target_TOS_SR_plot,
  group_levels = levels(
    Bolzano_target_TOS_SR$Target_Waste_Category
  )
)

y_axis_TOS_SR



#######################################
## Boxplot: Total organics separation
## rate by target waste category
#######################################

gg_target_TOS_SR <- ggplot(
  Bolzano_target_TOS_SR,
  aes(
    x = Target_Waste_Category,
    y = TOS_SR_2024
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
    color = "black",
    position = position_dodge(width = 0.75)
  ) +
  add_n_labels(
    y_position = y_axis_TOS_SR$n_label_y,
    size = 10,
    vjust = 0
  ) +
  add_plot_label(
    label = d_label_target_TOS_SR,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_significance_labels(
    test_results = ttest_target_TOS_SR_plot,
    y_positions = y_axis_TOS_SR$significance_y_positions,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_axis_TOS_SR$break_max,
      by = y_axis_TOS_SR$interval
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_axis_TOS_SR$y_max
    )
  ) +
  labs(
    x = "Target biowaste category",
    y = "Organics stream separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_target_TOS_SR



#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Target biowaste category on total organics separation rate_Bolzano.png"
  ),
  plot = gg_target_TOS_SR,
  width = 16,
  height = 9,
  dpi = 300
)



##########################################################################
### Residual waste composition
##########################################################################


#######################################
### Data preparation
#######################################

Bolzano_RWcomp_analysis <- BOLZANO_RWcomp %>%
  mutate(
    Target_Waste_Category = factor(
      Target_Waste_Category,
      levels = c(
        "Biowaste",
        "Food waste"
      )
    )
  ) %>%
  filter(
    !is.na(Target_Waste_Category),
    !is.na(SR_BWgross),
    !is.na(SR_TOSgross),
    !is.na(SR_BWapprox),
    !is.na(SR_TOSapprox)
  )

Bolzano_RWcomp_analysis


#################################################
### KPI 7: Approximate biowaste separation rate
#################################################


########################
### Summary
########################

Bolzano_RW_comp_summary <- summary_statistics(
  data = Bolzano_RWcomp_analysis,
  summary_var = "SR_BWapprox",
  group_var = "Target_Waste_Category",
  digits = 3
)

Bolzano_RW_comp_summary


#######################################
## Pairwise t-test
#######################################

ttest_RW_comp <- run_pairwise_t_test(
  data = Bolzano_RWcomp_analysis,
  response = "SR_BWapprox",
  group = "Target_Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_RW_comp


#######################################
## Effect size: Cohen's d
#######################################

d_RW_comp <- effectsize::cohens_d(
  SR_BWapprox ~ Target_Waste_Category,
  data = Bolzano_RWcomp_analysis,
  pooled_sd = FALSE
)

d_RW_comp






#################################################
### KPI 8: Approximate total organics separation rate
#################################################


########################
### Summary
########################

Bolzano_RW_comp_summary <- summary_statistics(
  data = Bolzano_RWcomp_analysis,
  summary_var = "SR_TOSapprox",
  group_var = "Target_Waste_Category",
  digits = 3
)

Bolzano_RW_comp_summary


#######################################
## Pairwise t-test
#######################################

ttest_RW_comp <- run_pairwise_t_test(
  data = Bolzano_RWcomp_analysis,
  response = "SR_TOSapprox",
  group = "Target_Waste_Category",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_RW_comp


#######################################
## Effect size: Cohen's d
#######################################

d_RW_comp <- effectsize::cohens_d(
  SR_TOSapprox ~ Target_Waste_Category,
  data = Bolzano_RWcomp_analysis,
  pooled_sd = FALSE
)

d_RW_comp








##################################################################
### Correlation analysis between KPIs
##################################################################

####################
### SR BWapprox
####################

BW_SR_relation <- run_scatter_lm_test(
  data = Bolzano_RWcomp_analysis,
  x = "SR_BWgross",
  y = "SR_BWapprox",
  digits = 2
)

BW_SR_relation$cor_result
summary(BW_SR_relation$lm_model)
BW_SR_relation$labels


#####################
### SR TOSapprox
#####################

TOS_SR_relation <- run_scatter_lm_test(
  data = Bolzano_RWcomp_analysis,
  x = "SR_TOSgross",
  y = "SR_TOSapprox",
  digits = 2
)

TOS_SR_relation$cor_result
summary(TOS_SR_relation$lm_model)
TOS_SR_relation$labels


###############################
### Summary
###############################

SR_correlation_results <- bind_rows(
  tibble(
    response = "SR_BWapprox",
    predictor = "SR_BWgross",
    n = nrow(BW_SR_relation$data),
    r = unname(
      BW_SR_relation$cor_result$estimate
    ),
    p = BW_SR_relation$cor_result$p.value,
    R2 = summary(
      BW_SR_relation$lm_model
    )$r.squared,
    intercept = unname(
      BW_SR_relation$intercept
    ),
    slope = unname(
      BW_SR_relation$slope
    )
  ),
  tibble(
    response = "SR_TOSapprox",
    predictor = "SR_TOSgross",
    n = nrow(TOS_SR_relation$data),
    r = unname(
      TOS_SR_relation$cor_result$estimate
    ),
    p = TOS_SR_relation$cor_result$p.value,
    R2 = summary(
      TOS_SR_relation$lm_model
    )$r.squared,
    intercept = unname(
      TOS_SR_relation$intercept
    ),
    slope = unname(
      TOS_SR_relation$slope
    )
  )
) %>%
  mutate(
    across(
      c(
        r,
        R2,
        intercept,
        slope
      ),
      ~ round(.x, 3)
    )
  )

SR_correlation_results



#######################################
### Scatter plot:
### Gross vs approximated biowaste
### separation rate
#######################################

gg_BW_SR <- ggplot(
  BW_SR_relation$data,
  aes(
    x = SR_BWgross,
    y = SR_BWapprox
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
    labels = BW_SR_relation$labels,
    position = "left",
    x_left = 0.02,
    y = Inf,
    vjust_start = 2,
    vjust_step = 2,
    size = 10
  ) +
  scale_x_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      1,
      by = 0.2
    ),
    labels = scales::label_number(
      scale = 100,
      accuracy = 1
    )
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      1,
      by = 0.2
    ),
    labels = scales::label_number(
      scale = 100,
      accuracy = 1
    )
  ) +
  coord_cartesian(
    xlim = c(0, 1.02),
    ylim = c(0, 1.02)
  ) +
  labs(
    x = "Biowaste stream separation rate [%]",
    y = "Aprx. net biowaste separation rate [%]"
  ) +
  theme_plot

gg_BW_SR


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Gross vs approximated biowaste separation rate_Bolzano.png"
  ),
  plot = gg_BW_SR,
  width = 16,
  height = 9,
  dpi = 300
)





#######################################
### Scatter plot:
### Gross vs approximated total
### organics separation rate
#######################################

gg_TOS_SR <- ggplot(
  TOS_SR_relation$data,
  aes(
    x = SR_TOSgross,
    y = SR_TOSapprox
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
    labels = TOS_SR_relation$labels,
    position = "left",
    x_left = 0.02,
    y = Inf,
    vjust_start = 2,
    vjust_step = 2,
    size = 10
  ) +
  scale_x_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      1,
      by = 0.2
    ),
    labels = scales::label_number(
      scale = 100,
      accuracy = 1
    )
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      1,
      by = 0.2
    ),
    labels = scales::label_number(
      scale = 100,
      accuracy = 1
    )
  ) +
  coord_cartesian(
    xlim = c(0, 1.02),
    ylim = c(0, 1.02)
  ) +
  labs(
    x = "Organics stream separation rate [%]",
    y = "Aprx. net organics separation rate [%]"
  ) +
  theme_plot

gg_TOS_SR


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Alto Adige",
    "Gross vs approximated total organics separation rate_Bolzano.png"
  ),
  plot = gg_TOS_SR,
  width = 16,
  height = 9,
  dpi = 300
)
