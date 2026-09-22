source("R/bootstrap.R")

###############
### Packages
###############

library(tidyverse)
library(ggplot2)
library(ggpubr)
library(rstatix)
library(car)
library(effectsize)
library(patchwork)
library(grid)
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
### Theme
###############################

if (.Platform$OS.type == "windows") {
  windowsFonts(
    Calibri = windowsFont("Calibri")
  )
}

theme_set(
  theme_minimal(
    base_family = "sans"
  )
)


################
### Raw data
################

Sweden <- read.csv(
  file = brit_path(
    "data",
    "raw",
    "Sweden",
    "BRIT_Sweden_Data update 2024.csv"
  ),
  na.strings = "#NV",
  header = TRUE, 
  sep = ";",
  dec = ".",
  fileEncoding = "Windows-1252")



#######################################
## Descriptive statistics
#######################################

###########
### KPIs
###########


#Food waste quantities, DtD

FW_quantity_summary <- Sweden %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category == "Food waste"
  ) %>%
  summary_statistics(
    summary_var = "Specific_Waste_Collected_2024",
    digits = 1
  )

FW_quantity_summary


# Residual waste quantities, DtD

RW_quantity_summary <- Sweden %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category == "Residual waste"
  ) %>%
  summary_statistics(
    summary_var = "Specific_Waste_Collected_2024",
    digits = 1
  )

RW_quantity_summary


#Separation rate, DtD

SR_summary <- Sweden %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category == "Food waste"
  ) %>%
  summary_statistics(
    summary_var = "Separation_rate",
    digits = 1
  )

SR_summary


### IFs


#IF: Food waste collection mode
FW_sepcol <- Sweden %>%
  filter(
    Waste_Category == "Food waste",
    !is.na(Collection_System),
    Collection_System != ""
  ) %>%
  summarise_population_distribution(
    category_var = "Collection_System",
    area_var = "Catchment",
    population_var = "Population_2024",
    sort_by = "entries_desc"
  )

FW_sepcol


# IF: Collection container configuration
container_config_stats <- Sweden %>%
  filter(
    Waste_Category == "Food waste",
    !is.na(Collection_container_config),
    Collection_container_config != ""
  ) %>%
  summarise_population_distribution(
    category_var = "Collection_container_config",
    area_var = "Catchment",
    population_var = "Population_2024",
    sort_by = "entries_desc"
  )

container_config_stats


##############################################################################
### Collection container configuration
##############################################################################

################################
### Setup
################################

# Factor order for boxplots
ccc_levels <- c(
  "Optical bag sorting",
  "Four compartments bin",
  "Two compartments bin",
  "Separate bins"
)

# X-axis labels
ccc_labels <- c(
  "Four compartments bin" = "4-compartments\nbin",
  "Two compartments bin" = "2-compartments\nbin",
  "Optical bag sorting" = "Optical\nbag sorting",
  "Separate bins" = "Separate\nbins"
)


##############################################
### KPI 1: Food waste
##############################################

#######################################
## Data preparation
#######################################

Sweden_CCC_FW <- Sweden %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category == "Food waste",
    !is.na(Collection_container_config),
    Collection_container_config != "",
    !is.na(Specific_Waste_Collected_2024)
  ) %>%
  mutate(
    Collection_container_config = trimws(Collection_container_config),
    Collection_container_config = factor(
      Collection_container_config,
      levels = ccc_levels
    )
  )

Sweden_CCC_FW


#######################################
## Summary statistics
#######################################

CCC_FW_summary <- summary_statistics(
  data = Sweden_CCC_FW,
  summary_var = "Specific_Waste_Collected_2024",
  group_var = "Collection_container_config",
  digits = 1
)

CCC_FW_summary



#######################################
## ANOVA assumption check and testing
#######################################

Sweden_CCC_FW_test <- run_oneway_test(
  data = Sweden_CCC_FW,
  response = "Specific_Waste_Collected_2024",
  group = "Collection_container_config"
)


# Extract individual results
levene_result_FW <- Sweden_CCC_FW_test$levene_result
levene_p_FW <- Sweden_CCC_FW_test$levene_p

anova_model_FW <- Sweden_CCC_FW_test$anova_model
anova_result_FW <- Sweden_CCC_FW_test$anova_result
anova_method_FW <- Sweden_CCC_FW_test$anova_method
anova_p_FW <- Sweden_CCC_FW_test$anova_p

levene_result_FW
anova_method_FW
anova_result_FW


# ANOVA label for boxplot
anova_label_FW <- format_anova_label(
  p = anova_p_FW,
  method = anova_method_FW
)

anova_label_FW



#######################################
## Pairwise significance testing
#######################################

# Complete, unfiltered test results
pairwise_t_results_FW <- run_pairwise_t_test(
  data = Sweden_CCC_FW,
  response = "Specific_Waste_Collected_2024",
  group = "Collection_container_config",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_t_results_FW


# Filtered pairwise results for boxplot
pairwise_t_results_FW_plot <- pairwise_t_results_FW %>%
  filter(
    p.adj.signif != "ns"
  )

pairwise_t_results_FW_plot


#######################################
## Effect size: Eta squared
#######################################

eta2_FW <- effectsize::eta_squared(
  anova_model_FW,
  partial = FALSE
)

eta2_FW


# Label for boxplot
eta2_label_FW <- eta2_FW %>%
  transmute(
    label = paste0(
      "\u03b7\u00b2 = ",
      round(Eta2, 2)
    )
  ) %>%
  pull(label)

eta2_label_FW



#######################################
## Y-axis preparation
#######################################


#######################################
## Y-axis preparation
#######################################

y_axis_FW <- prepare_y_axis_quantity_compact_significance(
  data = Sweden_CCC_FW,
  value_var = "Specific_Waste_Collected_2024",
  interval = 10,
  test_results = pairwise_t_results_FW_plot,
  group_levels = ccc_levels,
  n_label_offset = 0.5,
  significance_start_offset = 1.5,
  significance_step_offset = 1,
  top_offset = 1
)




#######################################
## Boxplot: Food waste quantities by collection container configuration
#######################################

gg_CCC_FW <- ggplot(
  Sweden_CCC_FW,
  aes(
    x = Collection_container_config,
    y = Specific_Waste_Collected_2024
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
    label = anova_label_FW,
    vjust = 1,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_FW,
    vjust = 3,
    size = 10
  ) +
  add_n_labels(
    y_position = y_axis_FW$n_label_y,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_t_results_FW_plot,
    y_positions = y_axis_FW$significance_y_positions,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_axis_FW$break_max,
      by = y_axis_FW$interval
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_axis_FW$y_max)
  ) +
  labs(
    x = "Collection container configuration",
    y = bquote(
      "Food waste stream [" *
        kg ~ inh^{-1} ~ a^{-1} *
        "]"
    )
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  ) +
  scale_x_discrete(
    labels = ccc_labels
  )

gg_CCC_FW


#######################################
## Save plot
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Sweden",
    "Collection container configuration_FW quantity.png"
  ),
  gg_CCC_FW,
  width = 16,
  height = 9,
  dpi = 300
)



#############################################################################
### KPI 2: Residual waste
#############################################################################

##########################################################
### Data preparation
##########################################################

# Collection container configuration per catchment
Sweden_CCC_lookup <- Sweden %>%
  mutate(
    Waste_Category = trimws(Waste_Category),
    Collection_System = trimws(Collection_System),
    Collection_container_config_lookup = trimws(Collection_container_config),
    Collection_container_config_lookup = factor(
      Collection_container_config_lookup,
      levels = ccc_levels
    )
  ) %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category == "Food waste",
    !is.na(Collection_container_config_lookup),
    Collection_container_config_lookup != ""
  ) %>%
  distinct(
    Catchment,
    Collection_container_config_lookup
  )


# Link collection container configuration to residual waste
Sweden_CCC_RW <- Sweden %>%
  mutate(
    Waste_Category = trimws(Waste_Category),
    Collection_System = trimws(Collection_System)
  ) %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category == "Residual waste",
    !is.na(Specific_Waste_Collected_2024)
  ) %>%
  left_join(
    Sweden_CCC_lookup,
    by = "Catchment"
  ) %>%
  filter(
    !is.na(Collection_container_config_lookup)
  ) %>%
  mutate(
    Collection_container_config = Collection_container_config_lookup
  ) %>%
  distinct(
    Catchment,
    Collection_container_config,
    Specific_Waste_Collected_2024
  )

Sweden_CCC_RW


#######################################
## Summary statistics
#######################################

CCC_RW_summary <- summary_statistics(
  data = Sweden_CCC_RW,
  summary_var = "Specific_Waste_Collected_2024",
  group_var = "Collection_container_config",
  digits = 1
)

CCC_RW_summary


#######################################
## ANOVA assumption check and testing
#######################################

Sweden_CCC_RW_test <- run_oneway_test(
  data = Sweden_CCC_RW,
  response = "Specific_Waste_Collected_2024",
  group = "Collection_container_config"
)


# Extract individual results
levene_result_RW <- Sweden_CCC_RW_test$levene_result
levene_p_RW <- Sweden_CCC_RW_test$levene_p

anova_model_RW <- Sweden_CCC_RW_test$anova_model
anova_result_RW <- Sweden_CCC_RW_test$anova_result
anova_method_RW <- Sweden_CCC_RW_test$anova_method
anova_p_RW <- Sweden_CCC_RW_test$anova_p

levene_result_RW
anova_method_RW
anova_result_RW


# ANOVA label for boxplot
anova_label_RW <- format_anova_label(
  p = anova_p_RW,
  method = anova_method_RW
)

anova_label_RW


#######################################
## Pairwise significance testing
#######################################

# Complete, unfiltered test results
pairwise_t_results_RW <- run_pairwise_t_test(
  data = Sweden_CCC_RW,
  response = "Specific_Waste_Collected_2024",
  group = "Collection_container_config",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_t_results_RW


# Filtered pairwise results for boxplot
pairwise_t_results_RW_plot <- pairwise_t_results_RW %>%
  filter(
    p.adj.signif != "ns"
  )

pairwise_t_results_RW_plot



#######################################
## Effect size: Eta squared
#######################################

eta2_RW <- effectsize::eta_squared(
  anova_model_RW,
  partial = FALSE
)

eta2_RW


# Label for boxplot
eta2_label_RW <- eta2_RW %>%
  transmute(
    label = paste0(
      "\u03b7\u00b2 = ",
      round(Eta2, 2)
    )
  ) %>%
  pull(label)

eta2_label_RW


#######################################
## Y-axis preparation
#######################################

y_axis_RW <- prepare_y_axis_quantity_compact_significance(
  data = Sweden_CCC_RW,
  value_var = "Specific_Waste_Collected_2024",
  interval = 50,
  test_results = pairwise_t_results_RW_plot,
  group_levels = ccc_levels,
  n_label_offset = 0.5,
  significance_start_offset = 1.5,
  significance_step_offset = 1,
  top_offset = 1
)




#######################################
## Boxplot: Residual waste quantities by collection container configuration
#######################################

gg_CCC_RW <- ggplot(
  Sweden_CCC_RW,
  aes(
    x = Collection_container_config,
    y = Specific_Waste_Collected_2024
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
    label = anova_label_RW,
    vjust = 1,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_RW,
    vjust = 3,
    size = 10
  ) +
  add_n_labels(
    y_position = y_axis_RW$n_label_y,
    size = 10,
    vjust = 0
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
    x = "Collection container configuration",
    y = bquote(
      "Residual waste stream [" *
        kg ~ inh^{-1} ~ a^{-1} *
        "]"
    )
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  ) +
  scale_x_discrete(
    labels = ccc_labels
  )

gg_CCC_RW


#######################################
## Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Sweden",
    "Collection container configuration_RW quantity.png"
  ),
  gg_CCC_RW,
  width = 16,
  height = 9,
  dpi = 300
)


##############################################
### KPI 3: Separation rate
##############################################

############################
### Data preparation
############################

Sweden_CCC_SR <- Sweden %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category == "Food waste",
    !is.na(Collection_container_config),
    Collection_container_config != "",
    !is.na(Separation_rate)
  ) %>%
  mutate(
    Collection_container_config = trimws(Collection_container_config),
    Collection_container_config = factor(
      Collection_container_config,
      levels = ccc_levels
    )
  )

Sweden_CCC_SR



#######################################
## Summary statistics
#######################################

CCC_SR_summary <- Sweden_CCC_SR %>%
  summary_statistics(
    summary_var = "Separation_rate",
    group_var = "Collection_container_config",
    digits = 1
  )

CCC_SR_summary



#######################################
## ANOVA assumption check and testing
#######################################

Sweden_CCC_SR_test <- run_oneway_test(
  data = Sweden_CCC_SR,
  response = "Separation_rate",
  group = "Collection_container_config"
)


# Extract individual results
levene_result_SR <- Sweden_CCC_SR_test$levene_result
levene_p_SR <- Sweden_CCC_SR_test$levene_p

anova_model_SR <- Sweden_CCC_SR_test$anova_model
anova_result_SR <- Sweden_CCC_SR_test$anova_result
anova_method_SR <- Sweden_CCC_SR_test$anova_method
anova_p_SR <- Sweden_CCC_SR_test$anova_p

levene_result_SR
anova_method_SR
anova_result_SR


# ANOVA label for boxplot
anova_label_SR <- format_anova_label(
  p = anova_p_SR,
  method = anova_method_SR
)

anova_label_SR



#######################################
## Pairwise significance testing
#######################################

# Complete, unfiltered test results
pairwise_t_results_SR <- run_pairwise_t_test(
  data = Sweden_CCC_SR,
  response = "Separation_rate",
  group = "Collection_container_config",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_t_results_SR


# Filtered pairwise results for boxplot
pairwise_t_results_SR_plot <- pairwise_t_results_SR %>%
  filter(
    p.adj.signif != "ns"
  )

pairwise_t_results_SR_plot


#######################################
## Effect size: Eta squared
#######################################

eta2_SR <- effectsize::eta_squared(
  anova_model_SR,
  partial = FALSE
)

eta2_SR


# Label for boxplot
eta2_label_SR <- eta2_SR %>%
  transmute(
    label = paste0(
      "\u03b7\u00b2 = ",
      round(Eta2, 2)
    )
  ) %>%
  pull(label)

eta2_label_SR




#######################################
## Y-axis preparation
#######################################

y_axis_SR <- prepare_y_axis_percent(
  data = Sweden_CCC_SR,
  value_var = "Separation_rate",
  interval = 10,
  max_break = 100,
  min_break_max = NULL,
  test_results = pairwise_t_results_SR_plot,
  group_levels = ccc_levels,
  n_label_offset = 0.5,
  significance_start_offset = 1.5,
  significance_step_offset = 1,
  top_offset = 1,
  y_max_padding = 2
)



#######################################
## Boxplot: Separation rate by collection container configuration
#######################################

gg_CCC_SR <- ggplot(
  Sweden_CCC_SR,
  aes(
    x = Collection_container_config,
    y = Separation_rate
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
    label = anova_label_SR,
    vjust = 1,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_SR,
    vjust = 3,
    size = 10
  ) +
  add_significance_labels(
    test_results = pairwise_t_results_SR_plot,
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
    ylim = c(0, y_axis_SR$y_max)
  ) +
  labs(
    x = "Collection container configuration",
    y = "Biowaste stream separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  ) +
  scale_x_discrete(
    labels = ccc_labels
  )

gg_CCC_SR



#######################################
## Save plot
#######################################


ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Sweden",
    "Collection container configuration_SR.png"
  ),
  gg_CCC_SR,
  width = 16,
  height = 9,
  dpi = 300
)

