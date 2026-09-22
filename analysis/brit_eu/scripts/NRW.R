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
### Raw data
################

NRW <- read.csv(
  file = brit_path(
    "data",
    "raw",
    "NRW",
    "1_BRIT_Deutschland_NRW_2024.csv"
  ),
  na.strings = c("", "#NV"),
  header = TRUE,
  sep = ";",
  dec = ".",
  fileEncoding = "Windows-1252"
)



#######################################
### Basic data preparation
#######################################

NRW <- NRW %>%
  mutate(
    Collection_System = na_if(
      trimws(as.character(Collection_System)),
      ""
    ),
    Participation_policy = factor(
      trimws(as.character(Participation_policy)),
      levels = c(
        "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
        "VOLUNTARY"
      ),
      labels = c(
        "Mandatory",
        "Voluntary"
      )
    )
  )


NRW_BW_base <- NRW %>%
  filter(
    !is.na(Collection_System),
    Waste_Category %in% c("Biowaste", "Food waste")
  )


NRW_RW_base <- NRW %>%
  filter(
    !is.na(Collection_System),
    Waste_Category == "Residual waste"
  )


#######################################
### Descriptive statistics
#######################################

#####################
### KPIs
#####################

# Biowaste quantities

NRW_BW_summary <- NRW_BW_base %>%
  summary_statistics(
    summary_var = "Specific_Waste_2024_kg",
    digits = 1
  )

NRW_BW_summary


# Residual waste quantities

NRW_RW_summary <- NRW_RW_base %>%
  summary_statistics(
    summary_var = "Specific_Waste_2024_kg",
    digits = 1
  )

NRW_RW_summary


# Separation rate

NRW_SR_summary <- NRW_BW_base %>%
  distinct(
    NUTS_LAU,
    SR_2024
  ) %>%
  summary_statistics(
    summary_var = "SR_2024"
  )

NRW_SR_summary


#######################################
### Municipalities and population
### above/below 50% separation rate
#######################################

NRW_SR_50_distribution <- NRW_BW_base %>%
  filter(
    Collection_System != "No separate collection",
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

NRW_SR_50_distribution



#####################
### IFs
#####################

# IF: Biowaste collection mode

NRW_sepcol <- NRW_BW_base %>%
  summarise_population_distribution(
    category_var = "Collection_System",
    density_var = "Population_Density_2024",
    sort_by = "entries_desc"
  )

NRW_sepcol


# IF: Participation policy

NRW_policy_summary <- NRW_BW_base %>%
  filter(
    !is.na(Participation_policy)
  ) %>%
  summarise_population_distribution(
    category_var = "Participation_policy",
    density_var = "Population_Density_2024",
    sort_by = "entries_desc"
  )

NRW_policy_summary




#######################
### IF: Connection rate
#######################

#######################################
### Create last available connection rate
### for 2024 analysis
#######################################

connection_years <- 2024:2021

connection_rate_cols <- paste0(
  "Connection_Rate_",
  connection_years
)

connection_rate_unit_cols <- paste0(
  "Connection_Rate_",
  connection_years,
  "_Unit"
)


NRW <- NRW %>%
  mutate(
    across(
      all_of(connection_rate_cols),
      ~ as.numeric(
        na_if(
          trimws(as.character(.x)),
          ""
        )
      ),
      .names = "{.col}_clean"
    ),
    across(
      all_of(connection_rate_unit_cols),
      ~ na_if(
        trimws(as.character(.x)),
        ""
      ),
      .names = "{.col}_clean"
    ),
    Connection_Rate_2024_used = coalesce(
      Connection_Rate_2024_clean,
      Connection_Rate_2023_clean,
      Connection_Rate_2022_clean,
      Connection_Rate_2021_clean
    ),
    Connection_Rate_2024_used_year = case_when(
      !is.na(Connection_Rate_2024_clean) ~ 2024L,
      !is.na(Connection_Rate_2023_clean) ~ 2023L,
      !is.na(Connection_Rate_2022_clean) ~ 2022L,
      !is.na(Connection_Rate_2021_clean) ~ 2021L,
      TRUE ~ NA_integer_
    ),
    Connection_Rate_2024_used_unit = case_when(
      Connection_Rate_2024_used_year == 2024L ~ Connection_Rate_2024_Unit_clean,
      Connection_Rate_2024_used_year == 2023L ~ Connection_Rate_2023_Unit_clean,
      Connection_Rate_2024_used_year == 2022L ~ Connection_Rate_2022_Unit_clean,
      Connection_Rate_2024_used_year == 2021L ~ Connection_Rate_2021_Unit_clean,
      TRUE ~ NA_character_
    )
  )



#######################################
### Variables
#######################################

CR <- "Connection_Rate_2024_used"
CR_unit <- "Connection_Rate_2024_used_unit"
CR_year <- "Connection_Rate_2024_used_year"


#######################################
### Base data for connection rate summaries
#######################################

NRW_CR_data <- NRW %>%
  filter(
    Waste_Category %in% c("Biowaste", "Food waste"),
    Collection_System == "Door to door"
  ) %>%
  mutate(
    CR_value = as.numeric(.data[[CR]]),
    CR_unit_value = na_if(
      trimws(as.character(.data[[CR_unit]])),
      ""
    ),
    Population_connection_2024 = (CR_value / 100) * Population_2024
  ) %>%
  distinct(
    NUTS_LAU,
    Participation_policy,
    Population_2024,
    CR_value,
    CR_unit_value,
    Population_connection_2024
  )



#######################################
### Coverage: data availability
#######################################

NRW_connection_rate_coverage <- NRW_CR_data %>%
  summarise(
    total_collection_areas = n_distinct(NUTS_LAU),
    areas_with_connection_rate = sum(!is.na(CR_value)),
    share_areas_percent = round(
      areas_with_connection_rate /
        total_collection_areas *
        100,
      1
    ),
    total_population = sum(
      Population_2024,
      na.rm = TRUE
    ),
    population_with_connection_rate = sum(
      Population_2024[!is.na(CR_value)],
      na.rm = TRUE
    ),
    share_population_percent = round(
      population_with_connection_rate /
        total_population *
        100,
      1
    )
  )

NRW_connection_rate_coverage


#######################################
### Calculation basis
#######################################

NRW_connection_rate_basis <- NRW_CR_data %>%
  filter(
    !is.na(CR_value),
    !is.na(CR_unit_value)
  ) %>%
  summarise_population_distribution(
    category_var = "CR_unit_value",
    population_var = "Population_2024",
    sort_by = "entries_desc"
  ) %>%
  rename(
    connection_rate_unit = CR_unit_value,
    n_areas = n_entries
  )

NRW_connection_rate_basis



#######################################
### Connection rate summary
### by policy + total
#######################################

NRW_CR_summary_data <- bind_rows(
  NRW_CR_data %>%
    filter(
      !is.na(CR_value),
      !is.na(Participation_policy)
    ) %>%
    mutate(
      Group = as.character(Participation_policy)
    ),
  NRW_CR_data %>%
    filter(
      !is.na(CR_value)
    ) %>%
    mutate(
      Group = "Total"
    )
)


NRW_connection_rate_summary <- NRW_CR_summary_data %>%
  summary_statistics(
    summary_var = "CR_value",
    group_var = "Group",
    digits = 2
  ) %>%
  left_join(
    NRW_CR_summary_data %>%
      group_by(Group) %>%
      summarise(
        population_total = sum(
          Population_2024,
          na.rm = TRUE
        ),
        population_connected = round(
          sum(
            Population_connection_2024,
            na.rm = TRUE
          ),
          0
        ),
        weighted_connection_rate = round(
          sum(
            Population_connection_2024,
            na.rm = TRUE
          ) /
            sum(
              Population_2024,
              na.rm = TRUE
            ) *
            100,
          2
        ),
        .groups = "drop"
      ),
    by = "Group"
  ) %>%
  mutate(
    Group = factor(
      Group,
      levels = c("Mandatory", "Voluntary", "Total")
    )
  ) %>%
  arrange(Group)

NRW_connection_rate_summary






##############################################################
### Plotting: Connection rate & participation policy
##############################################################

#####################
### Data preparation
#####################

NRW_CR_part <- NRW_CR_data %>%
  filter(
    !is.na(CR_value),
    !is.na(Participation_policy)
  )

#######################################
## t-test: Connection rate by policy
#######################################

ttest_CR_policy <- run_pairwise_t_test(
  data = NRW_CR_part,
  response = "CR_value",
  group = "Participation_policy",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_CR_policy

ttest_CR_policy_plot <- ttest_CR_policy %>%
  filter(p.adj.signif != "ns")


#######################################
### Effect size: Cohen's d
#######################################

d_CR_policy <- effectsize::cohens_d(
  CR_value ~ Participation_policy,
  data = NRW_CR_part
)

d_CR_policy

d_label_CR_policy <- paste0(
  "Cohen's d = ",
  round(d_CR_policy$Cohens_d, 1)
)


#######################################
## Y-axis preparation
#######################################

y_interval_CR <- 20

y_break_max_CR <- 100

y_max_CR <- 120



##########################
### Boxplot CR vs policy
##########################

gg_CR_policy <- ggplot(
  NRW_CR_part,
  aes(x = Participation_policy, y = CR_value)
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
    label = d_label_CR_policy,
    hjust = 1.0,
    vjust = 1.2,
    size = 10
  ) +
  add_n_labels(
    y_position = y_max_CR * 0.86,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = ttest_CR_policy_plot,
    y_positions = y_max_CR * 0.93,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CR,
      by = y_interval_CR
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_max_CR)
  ) +
  labs(
    x = "Participation policy",
    y = "Connection rate [% of population]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_CR_policy

### Save

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Connection rate based on participation policy_NRW.png"
  ),
  plot = gg_CR_policy,
  width = 16,
  height = 9,
  dpi = 300
)



#################################
### Preparation data for total
#################################

NRW_CR_total <- NRW_CR_data %>%
  filter(
    !is.na(CR_value)
  ) %>%
  mutate(
    Group = factor(
      "Total",
      levels = "Total"
    )
  )

###################
### Total boxplot
###################

gg_CR_total <- ggplot(
  NRW_CR_total,
  aes(
    x = Group,
    y = CR_value
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
    y_position = y_max_CR * 0.86,
    size = 10,
    vjust = 0
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CR,
      by = y_interval_CR
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_max_CR)
  ) +
  labs(
    x = NULL,
    y = NULL
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0),
    axis.title.y = element_blank(),
    axis.text.y = element_blank(),
    axis.ticks.y = element_blank()
  )

gg_CR_total

######################################################
### Boxplot combination: total & participation policy
######################################################

gg_CR_policy_total <- gg_CR_policy + gg_CR_total +
  plot_layout(
    widths = c(2, 1)
  )

gg_CR_policy_total


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Connection rate based on participation policy and total_NRW.png"
  ),
  plot = gg_CR_policy_total,
  width = 16,
  height = 9,
  dpi = 300
)



############################################################################
### Statistical assessment KPI vs IF - Participation policy
############################################################################


###############################################
### KPI 1: Biowaste/Food waste quantities
###############################################

#####################
### Data preparation
#####################

NRW_policy_BW <- NRW_BW_base %>%
  filter(
    Collection_System == "Door to door",
    !is.na(Specific_Waste_2024_kg),
    !is.na(Participation_policy)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Participation_policy,
    Specific_Waste_2024_kg
  )

NRW_policy_BW

#######################################
### Summary
#######################################

NRW_policy_BW_summary <- NRW_policy_BW %>%
  summary_statistics(
    summary_var = "Specific_Waste_2024_kg",
    group_var = "Participation_policy",
    digits = 2
  )

NRW_policy_BW_summary


#######################################
### t-test
#######################################

ttest_policy_BW <- run_pairwise_t_test(
  data = NRW_policy_BW,
  response = "Specific_Waste_2024_kg",
  group = "Participation_policy",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_policy_BW

ttest_policy_BW_plot <- ttest_policy_BW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Cohen's d
#######################################

d_policy_BW <- effectsize::cohens_d(
  Specific_Waste_2024_kg ~ Participation_policy,
  data = NRW_policy_BW
)

d_policy_BW

d_label_policy_BW <- paste0(
  "Cohen's d = ",
  round(d_policy_BW$Cohens_d, 1)
)


#######################################
### Y-axis preparation
#######################################

y_interval_policy_BW <- 50
y_break_max_policy_BW <- 250
y_max_policy_BW <- 260


#######################################
### Boxplot: Biowaste/Food waste quantities by policy
#######################################

gg_policy_BW <- ggplot(
  NRW_policy_BW,
  aes(
    x = Participation_policy,
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
    label = d_label_policy_BW,
    hjust = 1.0,
    vjust = 1.2,
    size = 10
  ) +
  add_n_labels(
    y_position = y_max_policy_BW * 0.88,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = ttest_policy_BW_plot,
    y_positions = y_max_policy_BW * 0.96,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_policy_BW,
      by = y_interval_policy_BW
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_max_policy_BW)
  ) +
  labs(
    x = "Participation policy",
    y = bquote("Biowaste [" *kg ~ inh^{-1} ~ a^{-1} *"]")
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_policy_BW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Participation policy on biowaste quantities_NRW.png"
  ),
  plot = gg_policy_BW,
  width = 16,
  height = 9,
  dpi = 300
)






###############################################
### KPI 2: Residual waste quantities
###############################################

#####################
### Data preparation
#####################

policy_lookup_RW <- NRW_BW_base %>%
  filter(
    Collection_System == "Door to door",
    !is.na(Participation_policy)
  ) %>%
  distinct(
    NUTS_LAU,
    Participation_policy
  )


NRW_policy_RW <- NRW_RW_base %>%
  filter(
    Collection_System == "Door to door",
    !is.na(Specific_Waste_2024_kg)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Specific_Waste_2024_kg
  ) %>%
  left_join(
    policy_lookup_RW,
    by = "NUTS_LAU"
  ) %>%
  filter(
    !is.na(Participation_policy)
  )

NRW_policy_RW


#######################################
### Summary
#######################################

NRW_policy_RW_summary <- NRW_policy_RW %>%
  summary_statistics(
    summary_var = "Specific_Waste_2024_kg",
    group_var = "Participation_policy",
    digits = 2
  )

NRW_policy_RW_summary


#######################################
### t-test
#######################################

ttest_policy_RW <- run_pairwise_t_test(
  data = NRW_policy_RW,
  response = "Specific_Waste_2024_kg",
  group = "Participation_policy",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_policy_RW

ttest_policy_RW_plot <- ttest_policy_RW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Cohen's d
#######################################

d_policy_RW <- effectsize::cohens_d(
  Specific_Waste_2024_kg ~ Participation_policy,
  data = NRW_policy_RW
)

d_policy_RW

d_label_policy_RW <- paste0(
  "Cohen's d = ",
  round(d_policy_RW$Cohens_d, 1)
)


#######################################
### Y-axis preparation
#######################################

y_interval_policy_RW <- 50
y_break_max_policy_RW <- 350
y_max_policy_RW <- 360


#######################################
### Boxplot: Residual waste quantities by policy
#######################################

gg_policy_RW <- ggplot(
  NRW_policy_RW,
  aes(
    x = Participation_policy,
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
    label = d_label_policy_RW,
    hjust = 1.0,
    vjust = 1.2,
    size = 10
  ) +
  add_n_labels(
    y_position = y_max_policy_RW * 0.90,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = ttest_policy_RW_plot,
    y_positions = y_max_policy_RW * 0.97,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_policy_RW,
      by = y_interval_policy_RW
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_max_policy_RW)
  ) +
  labs(
    x = "Participation policy",
    y = bquote("Residual waste [" *kg ~ inh^{-1} ~ a^{-1} *"]")
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_policy_RW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Participation policy on residual waste quantities_NRW.png"
  ),
  plot = gg_policy_RW,
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

NRW_policy_SR <- NRW_BW_base %>%
  filter(
    Collection_System == "Door to door",
    !is.na(SR_2024),
    !is.na(Participation_policy)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Participation_policy,
    Population_2024,
    SR_2024
  )

NRW_policy_SR


#######################################
### Summary
#######################################

NRW_policy_SR_summary <- NRW_policy_SR %>%
  summary_statistics(
    summary_var = "SR_2024",
    group_var = "Participation_policy",
    digits = 2
  )

NRW_policy_SR_summary


#######################################
### t-test
#######################################

ttest_policy_SR <- run_pairwise_t_test(
  data = NRW_policy_SR,
  response = "SR_2024",
  group = "Participation_policy",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

ttest_policy_SR

ttest_policy_SR_plot <- ttest_policy_SR %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Cohen's d
#######################################

d_policy_SR <- effectsize::cohens_d(
  SR_2024 ~ Participation_policy,
  data = NRW_policy_SR
)

d_policy_SR

d_label_policy_SR <- paste0(
  "Cohen's d = ",
  round(d_policy_SR$Cohens_d, 1)
)


#######################################
### Y-axis preparation
#######################################

y_interval_policy_SR <- 20
y_break_max_policy_SR <- 100
y_max_policy_SR <- 105


#######################################
## Boxplot: Separation rate
#######################################

#######################################
### Boxplot: Separation rate by policy
#######################################

gg_policy_SR <- ggplot(
  NRW_policy_SR,
  aes(
    x = Participation_policy,
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
  add_plot_label(
    label = d_label_policy_SR,
    hjust = 1.0,
    vjust = 1.2,
    size = 10
  ) +
  add_n_labels(
    y_position = y_max_policy_SR * 0.84,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = ttest_policy_SR_plot,
    y_positions = y_max_policy_SR * 0.92,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_policy_SR,
      by = y_interval_policy_SR
    )
  ) +
  coord_cartesian(
    ylim = c(0, y_max_policy_SR)
  ) +
  labs(
    x = "Participation policy",
    y = "Biowaste stream separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(angle = 0)
  )

gg_policy_SR


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Participation policy on Biowaste stream Separation rate_NRW.png"
  ),
  plot = gg_policy_SR,
  width = 16,
  height = 9,
  dpi = 300
)




############################################################################
### Statistical assessment KPI vs IF - Biowaste population connection rate
############################################################################

####################################
### Define connection rate value
####################################

NRW_CR_BW_base <- NRW_BW_base %>%
  filter(
    Collection_System == "Door to door"
  ) %>%
  mutate(
    CR_2024_value = as.numeric(
      na_if(
        trimws(as.character(Connection_Rate_2024)),
        ""
      )
    )
  )


#######################################
### X-axis preparation
#######################################

x_interval_CR <- 20
x_break_max_CR <- 100
x_max_CR <- 102


###############################################
### KPI 1: Biowaste/Food waste quantities
###############################################

#####################
### Data preparation
#####################

NRW_CR_BW <- NRW_CR_BW_base %>%
  filter(
    !is.na(CR_2024_value),
    !is.na(Specific_Waste_2024_kg)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    CR_2024_value,
    Specific_Waste_2024_kg
  )

NRW_CR_BW


#######################################
### Summary
#######################################

NRW_CR_BW_summary <- NRW_CR_BW %>%
  summary_statistics(
    summary_var = "Specific_Waste_2024_kg",
    digits = 2
  )

NRW_CR_BW_summary


#######################################
### Correlation test and linear model
#######################################

lm_CR_BW_result <- run_scatter_lm_test(
  data = NRW_CR_BW,
  x = "CR_2024_value",
  y = "Specific_Waste_2024_kg"
)

cor_CR_BW <- lm_CR_BW_result$cor_result
lm_CR_BW <- lm_CR_BW_result$lm_model

cor_CR_BW
summary(lm_CR_BW)

#######################################
### Y-axis preparation
#######################################

y_interval_CR_BW <- 50
y_break_max_CR_BW <- 250
y_max_CR_BW <- 260



#######################################
### Scatter plot: Connection rate vs biowaste quantities
#######################################

gg_CR_BW <- ggplot(
  NRW_CR_BW,
  aes(
    x = CR_2024_value,
    y = Specific_Waste_2024_kg
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
    se = FALSE,
    color = "black",
    linewidth = 1.5
  ) +
  add_scatter_lm_labels(
    labels = lm_CR_BW_result$labels,
    slope = lm_CR_BW_result$slope,
    position = "auto"
  ) +
  scale_x_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      x_break_max_CR,
      by = x_interval_CR
    )
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CR_BW,
      by = y_interval_CR_BW
    )
  ) +
  coord_cartesian(
    xlim = c(0, x_max_CR),
    ylim = c(0, y_max_CR_BW)
  ) +
  labs(
    x = "Population connection rate [%]",
    y = bquote("Biowaste [" *kg ~ inh^{-1} ~ a^{-1} *"]")
  ) +
  theme_plot

gg_CR_BW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Connection rate on biowaste quantities_NRW.png"
  ),
  plot = gg_CR_BW,
  width = 16,
  height = 9,
  dpi = 300
)




###############################################
### KPI 2: Residual waste quantities
###############################################

#####################
### Data preparation
#####################

CR_lookup_RW <- NRW_CR_BW_base %>%
  filter(
    !is.na(CR_2024_value)
  ) %>%
  distinct(
    NUTS_LAU,
    CR_2024_value
  )


NRW_CR_RW <- NRW_RW_base %>%
  filter(
    Collection_System == "Door to door",
    !is.na(Specific_Waste_2024_kg)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Specific_Waste_2024_kg
  ) %>%
  left_join(
    CR_lookup_RW,
    by = "NUTS_LAU"
  ) %>%
  filter(
    !is.na(CR_2024_value)
  )

NRW_CR_RW


#######################################
### Check lookup
#######################################

CR_lookup_RW %>%
  count(NUTS_LAU) %>%
  filter(
    n > 1
  )


#######################################
### Summary
#######################################

NRW_CR_RW_summary <- NRW_CR_RW %>%
  summary_statistics(
    summary_var = "Specific_Waste_2024_kg",
    digits = 2
  )

NRW_CR_RW_summary


#######################################
### Correlation test and linear model
#######################################

lm_CR_RW_result <- run_scatter_lm_test(
  data = NRW_CR_RW,
  x = "CR_2024_value",
  y = "Specific_Waste_2024_kg"
)

cor_CR_RW <- lm_CR_RW_result$cor_result
lm_CR_RW <- lm_CR_RW_result$lm_model

cor_CR_RW
summary(lm_CR_RW)


#######################################
### Y-axis preparation
#######################################

y_interval_CR_RW <- 50
y_break_max_CR_RW <- 350
y_max_CR_RW <- 360

#######################################
### Scatter plot: Connection rate vs residual waste quantities
#######################################

gg_CR_RW <- ggplot(
  NRW_CR_RW,
  aes(
    x = CR_2024_value,
    y = Specific_Waste_2024_kg
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
    se = FALSE,
    color = "black",
    linewidth = 1.5
  ) +
  add_scatter_lm_labels(
    labels = lm_CR_RW_result$labels,
    slope = lm_CR_RW_result$slope,
    position = "auto"
  ) +
  scale_x_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      x_break_max_CR,
      by = x_interval_CR
    )
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CR_RW,
      by = y_interval_CR_RW
    )
  ) +
  coord_cartesian(
    xlim = c(0, x_max_CR),
    ylim = c(0, y_max_CR_RW)
  ) +
  labs(
    x = "Population connection rate [%]",
    y = bquote("Residual waste [" *kg ~ inh^{-1} ~ a^{-1} *"]")
  ) +
  theme_plot

gg_CR_RW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Connection rate on residual waste quantities_NRW.png"
  ),
  plot = gg_CR_RW,
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

NRW_CR_SR <- NRW_CR_BW_base %>%
  filter(
    !is.na(CR_2024_value),
    !is.na(SR_2024)
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    CR_2024_value,
    SR_2024
  )

NRW_CR_SR



#######################################
### Summary
#######################################

NRW_CR_SR_summary <- NRW_CR_SR %>%
  summary_statistics(
    summary_var = "SR_2024",
    digits = 2
  )

NRW_CR_SR_summary


#######################################
### Correlation test and linear model
#######################################

lm_CR_SR_result <- run_scatter_lm_test(
  data = NRW_CR_SR,
  x = "CR_2024_value",
  y = "SR_2024"
)

cor_CR_SR <- lm_CR_SR_result$cor_result
lm_CR_SR <- lm_CR_SR_result$lm_model

cor_CR_SR
summary(lm_CR_SR)


#######################################
### Y-axis preparation
#######################################

y_interval_CR_SR <- 20
y_break_max_CR_SR <- 100
y_max_CR_SR <- 105



#######################################
### Scatter plot: Connection rate vs separation rate
#######################################

gg_CR_SR <- ggplot(
  NRW_CR_SR,
  aes(
    x = CR_2024_value,
    y = SR_2024
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
    se = FALSE,
    color = "black",
    linewidth = 1.5
  ) +
  add_scatter_lm_labels(
    labels = lm_CR_SR_result$labels,
    slope = lm_CR_SR_result$slope,
    position = "auto"
  ) +
  scale_x_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      x_break_max_CR,
      by = x_interval_CR
    )
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_CR_SR,
      by = y_interval_CR_SR
    )
  ) +
  coord_cartesian(
    xlim = c(0, x_max_CR),
    ylim = c(0, y_max_CR_SR)
  ) +
  labs(
    x = "Population connection rate [%]",
    y = "Biowaste stream separation rate [%]"
  ) +
  theme_plot

gg_CR_SR


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Connection rate on Biowaste stream Separation rate_NRW.png"
  ),
  plot = gg_CR_SR,
  width = 16,
  height = 9,
  dpi = 300
)


#####################################################################################################################
### ggfs code hier weit anpassen an helpers script
#####################################################################################################################






###################################################################
### Longitudinal analysis: Influence of change of connection rate 
### over years per collection area on change of quantities and SR 
###################################################################

############################################################################
### Longitudinal data preparation
############################################################################

years <- 2021:2024

connection_cols <- paste0("Connection_Rate_", years)
waste_cols <- paste0("Specific_Waste_", years, "_kg")
sr_cols <- paste0("SR_", years)


##############################
### Biowaste/Food waste data
##############################

NRW_BW_long <- NRW %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category %in% c("Biowaste", "Food waste")
  ) %>%
  select(
    NUTS_LAU,
    Catchment,
    all_of(connection_cols),
    all_of(waste_cols),
    all_of(sr_cols)
  ) %>%
  pivot_longer(
    cols = -c(NUTS_LAU, Catchment),
    names_to = c(".value", "Year"),
    names_pattern = "^(Connection_Rate|Specific_Waste|SR)_(\\d{4})(?:_kg)?$"
  ) %>%
  mutate(
    Year = as.integer(Year),
    Connection_Rate = as.numeric(Connection_Rate),
    Specific_Waste = as.numeric(Specific_Waste),
    SR = as.numeric(SR)
  ) %>%
  rename(
    Biowaste = Specific_Waste
  ) %>%
  distinct(
    NUTS_LAU,
    Catchment,
    Year,
    Connection_Rate,
    Biowaste,
    SR
  )


##############################
### Residual waste data
##############################

NRW_RW_long <- NRW %>%
  filter(
    Collection_System == "Door to door",
    Waste_Category == "Residual waste"
  ) %>%
  select(
    NUTS_LAU,
    Catchment,
    all_of(waste_cols)
  ) %>%
  pivot_longer(
    cols = all_of(waste_cols),
    names_to = "Year",
    names_pattern = "^Specific_Waste_(\\d{4})_kg$",
    values_to = "Residual_waste"
  ) %>%
  mutate(
    Year = as.integer(Year),
    Residual_waste = as.numeric(Residual_waste)
  ) %>%
  distinct(
    NUTS_LAU,
    Year,
    Residual_waste
  )


##############################
### Combined longitudinal dataset
##############################

NRW_long <- NRW_BW_long %>%
  left_join(
    NRW_RW_long,
    by = c("NUTS_LAU", "Year")
  ) %>%
  select(
    NUTS_LAU,
    Catchment,
    Year,
    Connection_Rate,
    Biowaste,
    Residual_waste,
    SR
  ) %>%
  arrange(
    NUTS_LAU,
    Year
  )

NRW_long


############################################################################
### Longitudinal delta analysis: 2021 to 2024
############################################################################

start_year <- 2021
end_year <- 2024


#######################################
### Create 2021-2024 wide dataset
#######################################

NRW_delta_2021_2024 <- NRW_long %>%
  filter(
    Year %in% c(start_year, end_year)
  ) %>%
  pivot_wider(
    id_cols = c(NUTS_LAU, Catchment),
    names_from = Year,
    values_from = c(
      Connection_Rate,
      Biowaste,
      Residual_waste,
      SR
    ),
    names_sep = "_"
  ) %>%
  mutate(
    delta_connection_rate = Connection_Rate_2024 - Connection_Rate_2021,
    delta_biowaste = Biowaste_2024 - Biowaste_2021,
    delta_residual_waste = Residual_waste_2024 - Residual_waste_2021,
    delta_SR = SR_2024 - SR_2021
  )

NRW_delta_2021_2024



#######################################
### Check valid delta pairs
#######################################

NRW_delta_2021_2024 %>%
  summarise(
    n_collection_areas = n(),
    
    n_delta_connection_rate = sum(!is.na(delta_connection_rate)),
    
    n_delta_biowaste = sum(
      !is.na(delta_connection_rate) &
        !is.na(delta_biowaste)
    ),
    
    n_delta_residual_waste = sum(
      !is.na(delta_connection_rate) &
        !is.na(delta_residual_waste)
    ),
    
    n_delta_SR = sum(
      !is.na(delta_connection_rate) &
        !is.na(delta_SR)
    )
  )


###############################################
### KPI 1: Delta biowaste quantities
###############################################

NRW_delta_BW <- NRW_delta_2021_2024 %>%
  filter(
    !is.na(delta_connection_rate),
    !is.na(delta_biowaste)
  ) %>%
  select(
    NUTS_LAU,
    Catchment,
    delta_connection_rate,
    delta_biowaste
  )

NRW_delta_BW


###############################################
### KPI 2: Delta residual waste quantities
###############################################

NRW_delta_RW <- NRW_delta_2021_2024 %>%
  filter(
    !is.na(delta_connection_rate),
    !is.na(delta_residual_waste)
  ) %>%
  select(
    NUTS_LAU,
    Catchment,
    delta_connection_rate,
    delta_residual_waste
  )

NRW_delta_RW


###############################################
### KPI 3: Delta separation rate
###############################################

NRW_delta_SR <- NRW_delta_2021_2024 %>%
  filter(
    !is.na(delta_connection_rate),
    !is.na(delta_SR)
  ) %>%
  select(
    NUTS_LAU,
    Catchment,
    delta_connection_rate,
    delta_SR
  )

NRW_delta_SR


############################################################################
### Longitudinal assessment: Delta connection rate vs delta KPI
############################################################################

###############################################
### KPI 1: Delta biowaste quantities
###############################################

#######################################
### Summary
#######################################

summary_var <- "delta_biowaste"

NRW_delta_BW %>%
  summarise(
    n = sum(!is.na(.data[[summary_var]])),
    min = round(min(.data[[summary_var]], na.rm = TRUE), 2),
    q1 = round(quantile(.data[[summary_var]], 0.25, na.rm = TRUE), 2),
    median = round(median(.data[[summary_var]], na.rm = TRUE), 2),
    mean = round(mean(.data[[summary_var]], na.rm = TRUE), 2),
    q3 = round(quantile(.data[[summary_var]], 0.75, na.rm = TRUE), 2),
    max = round(max(.data[[summary_var]], na.rm = TRUE), 2),
    sd = round(sd(.data[[summary_var]], na.rm = TRUE), 2)
  )


#######################################
### Correlation test
#######################################

cor_delta_BW <- cor.test(
  NRW_delta_BW$delta_connection_rate,
  NRW_delta_BW$delta_biowaste,
  method = "pearson"
)

cor_delta_BW


#######################################
### Linear model
#######################################

lm_delta_BW <- lm(
  delta_biowaste ~ delta_connection_rate,
  data = NRW_delta_BW
)

summary(lm_delta_BW)


#######################################
### Labels for scatter plot
#######################################

intercept_delta_BW <- coef(lm_delta_BW)[1]
slope_delta_BW <- coef(lm_delta_BW)[2]

cor_label_delta_BW <- paste0(
  "Pearson r = ",
  round(unname(cor_delta_BW$estimate), 2),
  "; p = ",
  format.pval(cor_delta_BW$p.value, digits = 2, eps = 0.001)
)

r2_label_delta_BW <- paste0(
  "R² = ",
  round(summary(lm_delta_BW)$r.squared, 2)
)

eq_label_delta_BW <- paste0(
  "y = ",
  round(slope_delta_BW, 2),
  "x ",
  ifelse(intercept_delta_BW >= 0, "+ ", "- "),
  abs(round(intercept_delta_BW, 2))
)


#######################################
### Scatter plot: Delta connection rate vs delta biowaste
#######################################

gg_delta_BW <- ggplot(
  NRW_delta_BW,
  aes(x = delta_connection_rate, y = delta_biowaste)
) +
  geom_hline(
    yintercept = 0,
    linewidth = 0.8,
    linetype = "dashed"
  ) +
  geom_vline(
    xintercept = 0,
    linewidth = 0.8,
    linetype = "dashed"
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
    se = FALSE,
    color = "black",
    linewidth = 1.5
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = cor_label_delta_BW,
    hjust = 1.05,
    vjust = 1.2,
    size = 10
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = r2_label_delta_BW,
    hjust = 1.05,
    vjust = 2.6,
    size = 10
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = eq_label_delta_BW,
    hjust = 1.05,
    vjust = 4.0,
    size = 10
  ) +
  labs(
    x = "Change in population connection rate [percentage points]",
    y = bquote("Change in biowaste ["*kg~inh^{-1}~a^{-1}*"]")
  ) +
  theme_plot

gg_delta_BW


### Save

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Delta connection rate on delta biowaste quantities_NRW.png"
  ),
  gg_delta_BW,
  width = 16,
  height = 9,
  dpi = 300
)



###############################################
### KPI 2: Delta residual waste quantities
###############################################

#######################################
### Summary
#######################################

summary_var <- "delta_residual_waste"

NRW_delta_RW %>%
  summarise(
    n = sum(!is.na(.data[[summary_var]])),
    min = round(min(.data[[summary_var]], na.rm = TRUE), 2),
    q1 = round(quantile(.data[[summary_var]], 0.25, na.rm = TRUE), 2),
    median = round(median(.data[[summary_var]], na.rm = TRUE), 2),
    mean = round(mean(.data[[summary_var]], na.rm = TRUE), 2),
    q3 = round(quantile(.data[[summary_var]], 0.75, na.rm = TRUE), 2),
    max = round(max(.data[[summary_var]], na.rm = TRUE), 2),
    sd = round(sd(.data[[summary_var]], na.rm = TRUE), 2)
  )


#######################################
### Correlation test
#######################################

cor_delta_RW <- cor.test(
  NRW_delta_RW$delta_connection_rate,
  NRW_delta_RW$delta_residual_waste,
  method = "pearson"
)

cor_delta_RW


#######################################
### Linear model
#######################################

lm_delta_RW <- lm(
  delta_residual_waste ~ delta_connection_rate,
  data = NRW_delta_RW
)

summary(lm_delta_RW)



#######################################
### Labels for scatter plot
#######################################

intercept_delta_RW <- coef(lm_delta_RW)[1]
slope_delta_RW <- coef(lm_delta_RW)[2]

cor_label_delta_RW <- paste0(
  "Pearson r = ",
  round(unname(cor_delta_RW$estimate), 2),
  "; p = ",
  format.pval(cor_delta_RW$p.value, digits = 2, eps = 0.001)
)

r2_label_delta_RW <- paste0(
  "R² = ",
  round(summary(lm_delta_RW)$r.squared, 2)
)

eq_label_delta_RW <- paste0(
  "y = ",
  round(slope_delta_RW, 2),
  "x ",
  ifelse(intercept_delta_RW >= 0, "+ ", "- "),
  abs(round(intercept_delta_RW, 2))
)


#######################################
### Scatter plot: Delta connection rate vs delta residual waste
#######################################

gg_delta_RW <- ggplot(
  NRW_delta_RW,
  aes(x = delta_connection_rate, y = delta_residual_waste)
) +
  geom_hline(
    yintercept = 0,
    linewidth = 0.8,
    linetype = "dashed"
  ) +
  geom_vline(
    xintercept = 0,
    linewidth = 0.8,
    linetype = "dashed"
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
    se = FALSE,
    color = "black",
    linewidth = 1.5
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = cor_label_delta_RW,
    hjust = 1.05,
    vjust = 1.2,
    size = 10
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = r2_label_delta_RW,
    hjust = 1.05,
    vjust = 2.6,
    size = 10
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = eq_label_delta_RW,
    hjust = 1.05,
    vjust = 4.0,
    size = 10
  ) +
  labs(
    x = "Change in population connection rate [percentage points]",
    y = bquote("Change in residual waste ["*kg~inh^{-1}~a^{-1}*"]")
  ) +
  theme_plot

gg_delta_RW


### Save

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Delta connection rate on delta residual waste quantities_NRW.png"
  ),
  gg_delta_RW,
  width = 16,
  height = 9,
  dpi = 300
)


###############################################
### KPI 3: Delta separation rate
###############################################

#######################################
### Summary
#######################################

summary_var <- "delta_SR"

NRW_delta_SR %>%
  summarise(
    n = sum(!is.na(.data[[summary_var]])),
    min = round(min(.data[[summary_var]], na.rm = TRUE), 2),
    q1 = round(quantile(.data[[summary_var]], 0.25, na.rm = TRUE), 2),
    median = round(median(.data[[summary_var]], na.rm = TRUE), 2),
    mean = round(mean(.data[[summary_var]], na.rm = TRUE), 2),
    q3 = round(quantile(.data[[summary_var]], 0.75, na.rm = TRUE), 2),
    max = round(max(.data[[summary_var]], na.rm = TRUE), 2),
    sd = round(sd(.data[[summary_var]], na.rm = TRUE), 2)
  )


#######################################
### Correlation test
#######################################

cor_delta_SR <- cor.test(
  NRW_delta_SR$delta_connection_rate,
  NRW_delta_SR$delta_SR,
  method = "pearson"
)

cor_delta_SR


#######################################
### Linear model
#######################################

lm_delta_SR <- lm(
  delta_SR ~ delta_connection_rate,
  data = NRW_delta_SR
)

summary(lm_delta_SR)


#######################################
### Labels for scatter plot
#######################################

intercept_delta_SR <- coef(lm_delta_SR)[1]
slope_delta_SR <- coef(lm_delta_SR)[2]

cor_label_delta_SR <- paste0(
  "Pearson r = ",
  round(unname(cor_delta_SR$estimate), 2),
  "; p = ",
  format.pval(cor_delta_SR$p.value, digits = 2, eps = 0.001)
)

r2_label_delta_SR <- paste0(
  "R² = ",
  round(summary(lm_delta_SR)$r.squared, 2)
)

eq_label_delta_SR <- paste0(
  "y = ",
  round(slope_delta_SR, 2),
  "x ",
  ifelse(intercept_delta_SR >= 0, "+ ", "- "),
  abs(round(intercept_delta_SR, 2))
)


#######################################
### Scatter plot: Delta connection rate vs delta separation rate
#######################################

gg_delta_SR <- ggplot(
  NRW_delta_SR,
  aes(x = delta_connection_rate, y = delta_SR)
) +
  geom_hline(
    yintercept = 0,
    linewidth = 0.8,
    linetype = "dashed"
  ) +
  geom_vline(
    xintercept = 0,
    linewidth = 0.8,
    linetype = "dashed"
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
    se = FALSE,
    color = "black",
    linewidth = 1.5
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = cor_label_delta_SR,
    hjust = 1.05,
    vjust = 1.2,
    size = 10
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = r2_label_delta_SR,
    hjust = 1.05,
    vjust = 2.6,
    size = 10
  ) +
  annotate(
    "text",
    x = Inf,
    y = Inf,
    label = eq_label_delta_SR,
    hjust = 1.05,
    vjust = 4.0,
    size = 10
  ) +
  labs(
    x = "Change in population connection rate [percentage points]",
    y = "Change in biowaste stream Separation Rate [percentage points]"
  ) +
  theme_plot

gg_delta_SR


### Save

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "NRW",
    "Delta connection rate on delta Biowaste stream Separation rate_NRW.png"
  ),
  gg_delta_SR,
  width = 16,
  height = 9,
  dpi = 300
)

