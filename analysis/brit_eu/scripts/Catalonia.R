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
### Data
################

Catalonia <- read.csv(
  file = brit_path(
    "data",
    if (getOption("brit.catalonia.rebuild", FALSE)) "processed" else "reference",
    "Catalonia",
    "BRIT_Katalonien_2024_merged_datasets_incl_impropis.csv"
  ),
  na.strings = c("", "#NV"),
  header = TRUE,
  sep = ";",
  dec = ".",
  fileEncoding = if (getOption("brit.catalonia.rebuild", FALSE)) "UTF-8-BOM" else "Windows-1252"
)


#######################################
### Basic data preparation
#######################################

Catalonia <- Catalonia %>%
  mutate(
    Collection_system_2024 = na_if(
      str_squish(
        as.character(Collection_system_2024)
      ),
      ""
    )
  )


#######################################
### Calculate separation rate
#######################################

# The gross biowaste separation rate is calculated from separately collected
# biowaste and residual waste quantities for each municipi.

Catalonia_SR <- Catalonia %>%
  filter(
    Waste_Category %in%
      c(
        "Biowaste",
        "Residual waste"
      )
  ) %>%
  select(
    codi,
    Catchment,
    Waste_Category,
    Quantity_2024_kg
  ) %>%
  pivot_wider(
    names_from = Waste_Category,
    values_from = Quantity_2024_kg
  ) %>%
  mutate(
    SR_2024 =
      `Biowaste` /
      (
        `Biowaste` +
          `Residual waste`
      ) *
      100
  ) %>%
  select(
    codi,
    SR_2024
  )


Catalonia <- Catalonia %>%
  left_join(
    Catalonia_SR,
    by = "codi",
    relationship = "many-to-one"
  )


#######################################
### Prepare base datasets
#######################################

# Biowaste base dataset used for biowaste quantities, impurity percentages,
# separation rates and influencing-factor analyses.

Catalonia_BW_base <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(Collection_system_2024),
    Collection_system_2024 !=
      "No separate collection"
  )


# Residual waste base dataset used for residual waste quantity analyses.

Catalonia_RW_base <- Catalonia %>%
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

Catalonia_BW_summary <- Catalonia_BW_base %>%
  filter(
    !is.na(Quantity_2024_kg)
  ) %>%
  summary_statistics(
    summary_var = "Quantity_2024_kg",
    digits = 1
  )

Catalonia_BW_summary


# Residual waste quantities

Catalonia_RW_summary <- Catalonia_RW_base %>%
  filter(
    !is.na(Quantity_2024_kg)
  ) %>%
  summary_statistics(
    summary_var = "Quantity_2024_kg",
    digits = 1
  )

Catalonia_RW_summary


# Biowaste impurities

Catalonia_Impropis_summary <- Catalonia_BW_base %>%
  filter(
    !is.na(
      Impurities_percentage_2024
    )
  ) %>%
  summary_statistics(
    summary_var =
      "Impurities_percentage_2024",
    digits = 1
  )

Catalonia_Impropis_summary


# Gross biowaste separation rate

Catalonia_SR_summary <- Catalonia_BW_base %>%
  filter(
    !is.na(SR_2024)
  ) %>%
  distinct(
    codi,
    SR_2024
  ) %>%
  summary_statistics(
    summary_var = "SR_2024",
    digits = 1
  )

Catalonia_SR_summary



#######################################
### Municipalities and population
### above/below 50% separation rate
#######################################

CAT_SR_50_distribution <- Catalonia_BW_base %>%
  filter(
    Collection_system_2024 != "No separate collection",
    !is.na(SR_2024)
  ) %>%
  distinct(
    codi,
    Population_2024,
    #Population_Density_2024,
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
    area_var = "codi",
    population_var = "Population_2024",
    #density_var = "Population_Density_2024",
    sort_by = "category"
  )

CAT_SR_50_distribution



#######################################
### Influencing factors
#######################################

#####################
### IF: Collection system
#####################

# Change these two variables to evaluate either 2024 or 2020.
#
# 2024:
collection_system_var <- "Collection_system_2024"
population_var <- "Population_2024"

# 2020:
#collection_system_var <- "Collection_system_2020"
#population_var <- "Population_2020"


Catalonia_collection_system <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(.data[[collection_system_var]])
  ) %>%
  distinct(
    codi,
    .data[[collection_system_var]],
    .data[[population_var]]
  ) %>%
  summarise_population_distribution(
    category_var = collection_system_var,
    area_var = "codi",
    population_var = population_var,
    sort_by = "entries_desc"
  )

Catalonia_collection_system


#######################################
### IF: Door-to-door connection rate (only mixed areas)
#######################################

Catalonia_PaP_connection <- Catalonia_BW_base %>%
  filter(
    Collection_system_2024 ==
      "Mixed Door-to-door and Bring point",
    !is.na(PaP_Connection_rate_2024)
  ) %>%
  distinct(
    codi,
    Catchment,
    Population_2024,
    PaP_Connection_rate_2024
  )


# Descriptive statistics

Catalonia_PaP_connection_summary <-
  Catalonia_PaP_connection %>%
  summary_statistics(
    summary_var = "PaP_Connection_rate_2024",
    digits = 1
  )

Catalonia_PaP_connection_summary


# Population-weighted mean

Catalonia_PaP_connection_weighted_mean <-
  Catalonia_PaP_connection %>%
  filter(
    !is.na(Population_2024)
  ) %>%
  summarise(
    weighted_mean =
      round(
        weighted.mean(
          PaP_Connection_rate_2024,
          Population_2024,
          na.rm = TRUE
        ),
        1
      )
  )

Catalonia_PaP_connection_weighted_mean



#######################################
### IF: Population split in mixed systems
#######################################

Catalonia_Mixed_population_split <- Catalonia_BW_base %>%
  filter(
    Collection_system_2024 ==
      "Mixed Door-to-door and Bring point",
    !is.na(PaP_Connection_rate_2024),
    !is.na(Population_2024)
  ) %>%
  distinct(
    codi,
    Catchment,
    Population_2024,
    PaP_Connection_rate_2024
  ) %>%
  summarise(
    total_population =
      sum(
        Population_2024,
        na.rm = TRUE
      ),
    
    DtD_population =
      sum(
        Population_2024 *
          PaP_Connection_rate_2024 / 100,
        na.rm = TRUE
      ),
    
    BP_population =
      sum(
        Population_2024 *
          (
            100 -
              PaP_Connection_rate_2024
          ) / 100,
        na.rm = TRUE
      )
  ) %>%
  mutate(
    DtD_population_share =
      round(
        DtD_population /
          total_population *
          100,
        1
      ),
    
    BP_population_share =
      round(
        BP_population /
          total_population *
          100,
        1
      )
  )

Catalonia_Mixed_population_split



#######################################
### Effective population shares
#######################################

Catalonia_effective_collection_system <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    Collection_system_2024 %in%
      c(
        "Door-to-door",
        "Bring point",
        "Mixed Door-to-door and Bring point",
        "Community composting",
        "No separate collection"
      ),
    !is.na(Population_2024)
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_system_2024,
    Population_2024,
    PaP_Connection_rate_2024
  ) %>%
  mutate(
    DtD_population = case_when(
      Collection_system_2024 ==
        "Door-to-door" ~
        Population_2024,
      
      Collection_system_2024 ==
        "Mixed Door-to-door and Bring point" &
        !is.na(PaP_Connection_rate_2024) ~
        Population_2024 *
        PaP_Connection_rate_2024 / 100,
      
      TRUE ~ 0
    ),
    
    BP_population = case_when(
      Collection_system_2024 ==
        "Bring point" ~
        Population_2024,
      
      Collection_system_2024 ==
        "Mixed Door-to-door and Bring point" &
        !is.na(PaP_Connection_rate_2024) ~
        Population_2024 *
        (
          100 -
            PaP_Connection_rate_2024
        ) / 100,
      
      TRUE ~ 0
    ),
    
    Community_composting_population = case_when(
      Collection_system_2024 ==
        "Community composting" ~
        Population_2024,
      
      TRUE ~ 0
    ),
    
    No_separate_collection_population = case_when(
      Collection_system_2024 ==
        "No separate collection" ~
        Population_2024,
      
      TRUE ~ 0
    )
  )


Catalonia_effective_collection_summary <-
  Catalonia_effective_collection_system %>%
  summarise(
    DtD_population =
      sum(
        DtD_population,
        na.rm = TRUE
      ),
    
    BP_population =
      sum(
        BP_population,
        na.rm = TRUE
      ),
    
    Community_composting_population =
      sum(
        Community_composting_population,
        na.rm = TRUE
      ),
    
    No_separate_collection_population =
      sum(
        No_separate_collection_population,
        na.rm = TRUE
      )
  ) %>%
  mutate(
    total_population =
      DtD_population +
      BP_population +
      Community_composting_population +
      No_separate_collection_population,
    
    DtD_population_share =
      round(
        DtD_population /
          total_population *
          100,
        1
      ),
    
    BP_population_share =
      round(
        BP_population /
          total_population *
          100,
        1
      ),
    
    Community_composting_population_share =
      round(
        Community_composting_population /
          total_population *
          100,
        1
      ),
    
    No_separate_collection_population_share =
      round(
        No_separate_collection_population /
          total_population *
          100,
        1
      )
  )

Catalonia_effective_collection_summary




Catalonia_effective_collection_system %>%
  filter(
    Collection_system_2024 ==
      "Mixed Door-to-door and Bring point",
    is.na(PaP_Connection_rate_2024)
  )






#####################
### IF: Door-to-door use control
#####################

Catalonia_PAP_control <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    Collection_system_2024 %in%
      c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point"
      )
  ) %>%
  mutate(
    PAP_Use_control_2024 = case_when(
      PAP_Use_control_2024 == "yes" ~
        "Yes",
      
      PAP_Use_control_2024 == "no" ~
        "No",
      
      PAP_Use_control_2024 == "x" ~
        "No information",
      
      TRUE ~
        NA_character_
    ),
    
    PAP_Use_control_2024 = factor(
      PAP_Use_control_2024,
      levels = c(
        "Yes",
        "No",
        "No information"
      )
    )
  ) %>%
  filter(
    !is.na(PAP_Use_control_2024)
  ) %>%
  distinct(
    codi,
    PAP_Use_control_2024,
    Population_2024
  )


Catalonia_PAP_control_summary <- Catalonia_PAP_control %>%
  summarise_population_distribution(
    category_var = "PAP_Use_control_2024",
    area_var = "codi",
    population_var = "Population_2024",
    sort_by = "category"
  )

Catalonia_PAP_control_summary



#####################
### IF: Bring point access control
#####################

Catalonia_BP_control <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    Collection_system_2024 %in%
      c(
        "Bring point",
        "Mixed Door-to-door and Bring point"
      )
  ) %>%
  mutate(
    BP_Access_control_2024 = case_when(
      BP_Access_control_2024 == "yes" ~
        "Yes",
      
      BP_Access_control_2024 == "no" ~
        "No",
      
      BP_Access_control_2024 == "x" ~
        "No information",
      
      TRUE ~
        NA_character_
    ),
    
    BP_Access_control_2024 = factor(
      BP_Access_control_2024,
      levels = c(
        "Yes",
        "No",
        "No information"
      )
    )
  ) %>%
  filter(
    !is.na(BP_Access_control_2024)
  ) %>%
  distinct(
    codi,
    BP_Access_control_2024,
    Population_2024
  )


Catalonia_BP_control_summary <- Catalonia_BP_control %>%
  summarise_population_distribution(
    category_var = "BP_Access_control_2024",
    area_var = "codi",
    population_var = "Population_2024",
    sort_by = "category"
  )

Catalonia_BP_control_summary



############################################################################
### Statistical assessment KPI vs IF - Collection mode
############################################################################



##################################################
### KPI 1: Biowaste/Food waste quantities
##################################################

#####################
### Data preparation
#####################

Catalonia_ColMod_BW <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(Quantity_2024_kg),
    Collection_system_2024 %in%
      c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point",
        "Bring point"
      )
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_system_2024,
    Population_2024,
    Quantity_2024_kg
  ) %>%
  mutate(
    Collection_system_2024 = factor(
      Collection_system_2024,
      levels = c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point",
        "Bring point"
      )
    ),
    Collection_system_2024 = droplevels(
      Collection_system_2024
    )
  )

Catalonia_ColMod_BW


#######################################
### Summary
#######################################

Catalonia_ColMod_BW_summary <- Catalonia_ColMod_BW %>%
  summary_statistics(
    summary_var = "Quantity_2024_kg",
    group_var = "Collection_system_2024",
    digits = 2
  )

Catalonia_ColMod_BW_summary


#######################################
### ANOVA
#######################################

anova_ColMod_BW <- run_oneway_test(
  data = Catalonia_ColMod_BW,
  response = "Quantity_2024_kg",
  group = "Collection_system_2024"
)


# Levene test

anova_ColMod_BW$levene_result

anova_ColMod_BW$levene_p


# Selected ANOVA method

anova_ColMod_BW$anova_method

anova_ColMod_BW$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_ColMod_BW <- run_pairwise_t_test(
  data = Catalonia_ColMod_BW,
  response = "Quantity_2024_kg",
  group = "Collection_system_2024",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_ColMod_BW


pairwise_ColMod_BW_plot <- pairwise_ColMod_BW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_ColMod_BW <- effectsize::eta_squared(
  anova_ColMod_BW$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_ColMod_BW


eta2_label_ColMod_BW <- paste0(
  "η² = ",
  round(
    eta2_ColMod_BW$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_ColMod_BW <- format_anova_label(
  p = anova_ColMod_BW$anova_p,
  method = anova_ColMod_BW$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_ColMod_BW


#######################################
### Y-axis preparation
#######################################

y_interval_ColMod_BW <- 50
y_break_max_ColMod_BW <- 400
y_max_ColMod_BW <- 420

n_label_y_ColMod_BW <- 335

significance_y_ColMod_BW <- c(
  365,
  385,
  365
)[
  seq_len(
    nrow(pairwise_ColMod_BW_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_ColMod_BW <- ggplot(
  Catalonia_ColMod_BW,
  aes(
    x = Collection_system_2024,
    y = Quantity_2024_kg
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
    label = anova_label_ColMod_BW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_ColMod_BW,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_ColMod_BW,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_ColMod_BW_plot,
    y_positions = significance_y_ColMod_BW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_ColMod_BW,
      by = y_interval_ColMod_BW
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_ColMod_BW
    )
  ) +
  scale_x_discrete(
    labels = c(
      "Door-to-door" =
        "Door-to-door",
      "Mixed Door-to-door and Bring point" =
        "Mixed",
      "Bring point" =
        "Bring point"
    )
  ) +
  labs(
    x = "Biowaste collection mode",
    y = bquote("Biowaste [" *kg ~ inh^{-1} ~ a^{-1} *"]"
    )
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_ColMod_BW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Catalonia",
    "Collection mode on biowaste quantities_Catalonia.png"
  ),
  plot = gg_ColMod_BW,
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

Catalonia_ColMod_RW <- Catalonia %>%
  filter(
    Waste_Category == "Residual waste",
    !is.na(Quantity_2024_kg),
    Collection_system_2024 %in%
      c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point",
        "Bring point"
      )
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_system_2024,
    Population_2024,
    Quantity_2024_kg
  ) %>%
  mutate(
    Collection_system_2024 = factor(
      Collection_system_2024,
      levels = c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point",
        "Bring point"
      )
    ),
    Collection_system_2024 = droplevels(
      Collection_system_2024
    )
  )

Catalonia_ColMod_RW


#######################################
### Summary
#######################################

Catalonia_ColMod_RW_summary <- Catalonia_ColMod_RW %>%
  summary_statistics(
    summary_var = "Quantity_2024_kg",
    group_var = "Collection_system_2024",
    digits = 2
  )

Catalonia_ColMod_RW_summary


#######################################
### ANOVA
#######################################

anova_ColMod_RW <- run_oneway_test(
  data = Catalonia_ColMod_RW,
  response = "Quantity_2024_kg",
  group = "Collection_system_2024"
)


# Levene test

anova_ColMod_RW$levene_result

anova_ColMod_RW$levene_p


# Selected ANOVA method

anova_ColMod_RW$anova_method

anova_ColMod_RW$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_ColMod_RW <- run_pairwise_t_test(
  data = Catalonia_ColMod_RW,
  response = "Quantity_2024_kg",
  group = "Collection_system_2024",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_ColMod_RW


pairwise_ColMod_RW_plot <- pairwise_ColMod_RW %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_ColMod_RW <- effectsize::eta_squared(
  anova_ColMod_RW$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_ColMod_RW


eta2_label_ColMod_RW <- paste0(
  "η² = ",
  round(
    eta2_ColMod_RW$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_ColMod_RW <- format_anova_label(
  p = anova_ColMod_RW$anova_p,
  method = anova_ColMod_RW$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_ColMod_RW


#######################################
### Y-axis preparation
#######################################

y_interval_ColMod_RW <- 200
y_break_max_ColMod_RW <- 1600
y_max_ColMod_RW <- 1650

n_label_y_ColMod_RW <- 1380

significance_y_ColMod_RW <- c(
  1475,
  1550,
  1475
)[
  seq_len(
    nrow(pairwise_ColMod_RW_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_ColMod_RW <- ggplot(
  Catalonia_ColMod_RW,
  aes(
    x = Collection_system_2024,
    y = Quantity_2024_kg
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
    label = anova_label_ColMod_RW,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_ColMod_RW,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_ColMod_RW,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_ColMod_RW_plot,
    y_positions = significance_y_ColMod_RW,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_ColMod_RW,
      by = y_interval_ColMod_RW
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_ColMod_RW
    )
  ) +
  scale_x_discrete(
    labels = c(
      "Door-to-door" =
        "Door-to-door",
      "Mixed Door-to-door and Bring point" =
        "Mixed",
      "Bring point" =
        "Bring point"
    )
  ) +
  labs(
    x = "Biowaste collection mode",
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

gg_ColMod_RW


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Catalonia",
    "Collection mode on residual waste quantities_Catalonia.png"
  ),
  plot = gg_ColMod_RW,
  width = 16,
  height = 9,
  dpi = 300
)



##################################################
### KPI 3: Biowaste stream separation rate
##################################################

#####################
### Data preparation
#####################

Catalonia_ColMod_SR <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(SR_2024),
    Collection_system_2024 %in%
      c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point",
        "Bring point"
      )
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_system_2024,
    Population_2024,
    SR_2024
  ) %>%
  mutate(
    Collection_system_2024 = factor(
      Collection_system_2024,
      levels = c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point",
        "Bring point"
      )
    ),
    Collection_system_2024 = droplevels(
      Collection_system_2024
    )
  )

Catalonia_ColMod_SR


#######################################
### Summary
#######################################

Catalonia_ColMod_SR_summary <- Catalonia_ColMod_SR %>%
  summary_statistics(
    summary_var = "SR_2024",
    group_var = "Collection_system_2024",
    digits = 2
  )

Catalonia_ColMod_SR_summary


#######################################
### ANOVA
#######################################

anova_ColMod_SR <- run_oneway_test(
  data = Catalonia_ColMod_SR,
  response = "SR_2024",
  group = "Collection_system_2024"
)


# Levene test

anova_ColMod_SR$levene_result

anova_ColMod_SR$levene_p


# Selected ANOVA method

anova_ColMod_SR$anova_method

anova_ColMod_SR$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_ColMod_SR <- run_pairwise_t_test(
  data = Catalonia_ColMod_SR,
  response = "SR_2024",
  group = "Collection_system_2024",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_ColMod_SR


pairwise_ColMod_SR_plot <- pairwise_ColMod_SR %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_ColMod_SR <- effectsize::eta_squared(
  anova_ColMod_SR$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_ColMod_SR


eta2_label_ColMod_SR <- paste0(
  "η² = ",
  round(
    eta2_ColMod_SR$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_ColMod_SR <- format_anova_label(
  p = anova_ColMod_SR$anova_p,
  method = anova_ColMod_SR$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_ColMod_SR


#######################################
### Y-axis preparation
#######################################

y_interval_ColMod_SR <- 20
y_break_max_ColMod_SR <- 100
y_max_ColMod_SR <- 112

n_label_y_ColMod_SR <- 92

significance_y_ColMod_SR <- c(
  100,
  105,
  100
)[
  seq_len(
    nrow(pairwise_ColMod_SR_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_ColMod_SR <- ggplot(
  Catalonia_ColMod_SR,
  aes(
    x = Collection_system_2024,
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
    label = anova_label_ColMod_SR,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_ColMod_SR,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_ColMod_SR,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_ColMod_SR_plot,
    y_positions = significance_y_ColMod_SR,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_ColMod_SR,
      by = y_interval_ColMod_SR
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_ColMod_SR
    )
  ) +
  scale_x_discrete(
    labels = c(
      "Door-to-door" =
        "Door-to-door",
      "Mixed Door-to-door and Bring point" =
        "Mixed",
      "Bring point" =
        "Bring point"
    )
  ) +
  labs(
    x = "Biowaste collection mode",
    y = "Biowaste stream separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_ColMod_SR


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Catalonia",
    "Collection mode on biowaste stream separation rate_Catalonia.png"
  ),
  plot = gg_ColMod_SR,
  width = 16,
  height = 9,
  dpi = 300
)






##################################################
### KPI 4: Biowaste impurities
##################################################

#####################
### Data preparation
#####################

Catalonia_ColMod_Imp <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(Impurities_percentage_2024),
    Collection_system_2024 %in%
      c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point",
        "Bring point"
      )
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_system_2024,
    Population_2024,
    Impurities_percentage_2024
  ) %>%
  mutate(
    Collection_system_2024 = factor(
      Collection_system_2024,
      levels = c(
        "Door-to-door",
        "Mixed Door-to-door and Bring point",
        "Bring point"
      )
    ),
    Collection_system_2024 = droplevels(
      Collection_system_2024
    )
  )

Catalonia_ColMod_Imp


#######################################
### Summary
#######################################

Catalonia_ColMod_Imp_summary <- Catalonia_ColMod_Imp %>%
  summary_statistics(
    summary_var = "Impurities_percentage_2024",
    group_var = "Collection_system_2024",
    digits = 2
  )

Catalonia_ColMod_Imp_summary


#######################################
### ANOVA
#######################################

anova_ColMod_Imp <- run_oneway_test(
  data = Catalonia_ColMod_Imp,
  response = "Impurities_percentage_2024",
  group = "Collection_system_2024"
)


# Levene test

anova_ColMod_Imp$levene_result

anova_ColMod_Imp$levene_p


# Selected ANOVA method

anova_ColMod_Imp$anova_method

anova_ColMod_Imp$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_ColMod_Imp <- run_pairwise_t_test(
  data = Catalonia_ColMod_Imp,
  response = "Impurities_percentage_2024",
  group = "Collection_system_2024",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_ColMod_Imp


pairwise_ColMod_Imp_plot <- pairwise_ColMod_Imp %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_ColMod_Imp <- effectsize::eta_squared(
  anova_ColMod_Imp$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_ColMod_Imp


eta2_label_ColMod_Imp <- paste0(
  "η² = ",
  round(
    eta2_ColMod_Imp$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_ColMod_Imp <- format_anova_label(
  p = anova_ColMod_Imp$anova_p,
  method = anova_ColMod_Imp$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_ColMod_Imp


#######################################
### Y-axis preparation
#######################################

y_interval_ColMod_Imp <- 5
y_break_max_ColMod_Imp <- 40
y_max_ColMod_Imp <- 45

n_label_y_ColMod_Imp <- 34

significance_y_ColMod_Imp <- c(
  40,
  37,
  37
)[
  seq_len(
    nrow(pairwise_ColMod_Imp_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_ColMod_Imp <- ggplot(
  Catalonia_ColMod_Imp,
  aes(
    x = Collection_system_2024,
    y = Impurities_percentage_2024
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
    label = anova_label_ColMod_Imp,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_ColMod_Imp,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_ColMod_Imp,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_ColMod_Imp_plot,
    y_positions = significance_y_ColMod_Imp,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_ColMod_Imp,
      by = y_interval_ColMod_Imp
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_ColMod_Imp
    )
  ) +
  scale_x_discrete(
    labels = c(
      "Door-to-door" =
        "Door-to-door",
      "Mixed Door-to-door and Bring point" =
        "Mixed",
      "Bring point" =
        "Bring point"
    )
  ) +
  labs(
    x = "Biowaste collection mode",
    y = "Biowaste impurities [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_ColMod_Imp


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Catalonia",
    "Collection mode on biowaste impurities_Catalonia.png"
  ),
  plot = gg_ColMod_Imp,
  width = 16,
  height = 9,
  dpi = 300
)










############################################################################
### Statistical assessment KPI vs IF - Use/access control
############################################################################








##################################################
### KPI 3: Biowaste stream separation rate
##################################################

#####################
### Data preparation
#####################

Catalonia_Control_SR <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(SR_2024),
    Collection_system_2024 %in%
      c(
        "Door-to-door",
        "Bring point"
      )
  ) %>%
  mutate(
    Collection_control_config = case_when(
      Collection_system_2024 == "Door-to-door" &
        str_to_lower(
          str_squish(PAP_Use_control_2024)
        ) == "yes" ~
        "Door-to-door | Use control: yes",
      
      Collection_system_2024 == "Door-to-door" &
        str_to_lower(
          str_squish(PAP_Use_control_2024)
        ) == "no" ~
        "Door-to-door | Use control: no",
      
      Collection_system_2024 == "Bring point" &
        str_to_lower(
          str_squish(BP_Access_control_2024)
        ) == "yes" ~
        "Bring point | Access control: yes",
      
      Collection_system_2024 == "Bring point" &
        str_to_lower(
          str_squish(BP_Access_control_2024)
        ) == "no" ~
        "Bring point | Access control: no",
      
      TRUE ~ NA_character_
    ),
    
    Collection_control_config = factor(
      Collection_control_config,
      levels = c(
        "Door-to-door | Use control: yes",
        "Door-to-door | Use control: no",
        "Bring point | Access control: yes",
        "Bring point | Access control: no"
      )
    )
  ) %>%
  filter(
    !is.na(Collection_control_config)
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_control_config,
    Population_2024,
    SR_2024
  ) %>%
  mutate(
    Collection_control_config =
      droplevels(
        Collection_control_config
      )
  )

Catalonia_Control_SR


#######################################
### Summary
#######################################

Catalonia_Control_SR_summary <- Catalonia_Control_SR %>%
  summary_statistics(
    summary_var = "SR_2024",
    group_var = "Collection_control_config",
    digits = 2
  )

Catalonia_Control_SR_summary


#######################################
### ANOVA
#######################################

anova_Control_SR <- run_oneway_test(
  data = Catalonia_Control_SR,
  response = "SR_2024",
  group = "Collection_control_config"
)


# Levene test

anova_Control_SR$levene_result

anova_Control_SR$levene_p


# Selected ANOVA method

anova_Control_SR$anova_method

anova_Control_SR$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_Control_SR <- run_pairwise_t_test(
  data = Catalonia_Control_SR,
  response = "SR_2024",
  group = "Collection_control_config",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_Control_SR


pairwise_Control_SR_plot <- pairwise_Control_SR %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_Control_SR <- effectsize::eta_squared(
  anova_Control_SR$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_Control_SR


eta2_label_Control_SR <- paste0(
  "η² = ",
  round(
    eta2_Control_SR$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_Control_SR <- format_anova_label(
  p = anova_Control_SR$anova_p,
  method = anova_Control_SR$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_Control_SR


#######################################
### Y-axis preparation
#######################################

y_interval_Control_SR <- 20
y_break_max_Control_SR <- 100
y_max_Control_SR <- 132

n_label_y_Control_SR <- 92

significance_y_Control_SR <- c(
  100,
  105,
  110,
  100,
  115,
  100
)[
  seq_len(
    nrow(pairwise_Control_SR_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_Control_SR <- ggplot(
  Catalonia_Control_SR,
  aes(
    x = Collection_control_config,
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
    label = anova_label_Control_SR,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_Control_SR,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_Control_SR,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_Control_SR_plot,
    y_positions = significance_y_Control_SR,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_Control_SR,
      by = y_interval_Control_SR
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_Control_SR
    )
  ) +
  scale_x_discrete(
    labels = c(
      "Door-to-door | Use control: yes" =
        "Door-to-door\nUse control",
      
      "Door-to-door | Use control: no" =
        "Door-to-door\nNo use control",
      
      "Bring point | Access control: yes" =
        "Bring point\nUse control",
      
      "Bring point | Access control: no" =
        "Bring point\nNo use control"
    )
  ) +
  labs(
    x = "Biowaste collection use control",
    y = "Biowaste stream separation rate [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_Control_SR


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Catalonia",
    "Use-access control on biowaste stream separation rate_Catalonia.png"
  ),
  plot = gg_Control_SR,
  width = 16,
  height = 9,
  dpi = 300
)






##################################################
### KPI 4: Biowaste impurities
##################################################

#####################
### Data preparation
#####################

Catalonia_Control_Imp <- Catalonia %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(Impurities_percentage_2024),
    Collection_system_2024 %in%
      c(
        "Door-to-door",
        "Bring point"
      )
  ) %>%
  mutate(
    Collection_control_config = case_when(
      Collection_system_2024 == "Door-to-door" &
        str_to_lower(
          str_squish(PAP_Use_control_2024)
        ) == "yes" ~
        "Door-to-door | Use control: yes",
      
      Collection_system_2024 == "Door-to-door" &
        str_to_lower(
          str_squish(PAP_Use_control_2024)
        ) == "no" ~
        "Door-to-door | Use control: no",
      
      Collection_system_2024 == "Bring point" &
        str_to_lower(
          str_squish(BP_Access_control_2024)
        ) == "yes" ~
        "Bring point | Access control: yes",
      
      Collection_system_2024 == "Bring point" &
        str_to_lower(
          str_squish(BP_Access_control_2024)
        ) == "no" ~
        "Bring point | Access control: no",
      
      TRUE ~ NA_character_
    ),
    
    Collection_control_config = factor(
      Collection_control_config,
      levels = c(
        "Door-to-door | Use control: yes",
        "Door-to-door | Use control: no",
        "Bring point | Access control: yes",
        "Bring point | Access control: no"
      )
    )
  ) %>%
  filter(
    !is.na(Collection_control_config)
  ) %>%
  distinct(
    codi,
    Catchment,
    Collection_control_config,
    Population_2024,
    Impurities_percentage_2024
  ) %>%
  mutate(
    Collection_control_config =
      droplevels(
        Collection_control_config
      )
  )

Catalonia_Control_Imp


#######################################
### Summary
#######################################

Catalonia_Control_Imp_summary <- Catalonia_Control_Imp %>%
  summary_statistics(
    summary_var = "Impurities_percentage_2024",
    group_var = "Collection_control_config",
    digits = 2
  )

Catalonia_Control_Imp_summary


#######################################
### ANOVA
#######################################

anova_Control_Imp <- run_oneway_test(
  data = Catalonia_Control_Imp,
  response = "Impurities_percentage_2024",
  group = "Collection_control_config"
)


# Levene test

anova_Control_Imp$levene_result

anova_Control_Imp$levene_p


# Selected ANOVA method

anova_Control_Imp$anova_method

anova_Control_Imp$anova_result


#######################################
### Pairwise t-tests
#######################################

pairwise_Control_Imp <- run_pairwise_t_test(
  data = Catalonia_Control_Imp,
  response = "Impurities_percentage_2024",
  group = "Collection_control_config",
  p_adjust = "bonferroni",
  pool_sd = FALSE
)

pairwise_Control_Imp


pairwise_Control_Imp_plot <- pairwise_Control_Imp %>%
  filter(
    p.adj.signif != "ns"
  )


#######################################
### Effect size: Eta squared
#######################################

eta2_Control_Imp <- effectsize::eta_squared(
  anova_Control_Imp$anova_model,
  partial = FALSE,
  ci = 0.95
)

eta2_Control_Imp


eta2_label_Control_Imp <- paste0(
  "η² = ",
  round(
    eta2_Control_Imp$Eta2[1],
    2
  )
)


#######################################
### ANOVA label
#######################################

anova_label_Control_Imp <- format_anova_label(
  p = anova_Control_Imp$anova_p,
  method = anova_Control_Imp$anova_method,
  show_method = FALSE,
  show_significance = FALSE
)

anova_label_Control_Imp


#######################################
### Y-axis preparation
#######################################

y_interval_Control_Imp <- 5
y_break_max_Control_Imp <- 35
y_max_Control_Imp <- 47

n_label_y_Control_Imp <- 34

significance_y_Control_Imp <- c(
  41,
  43,
  37,
  39,
  37,
  45
)[
  seq_len(
    nrow(pairwise_Control_Imp_plot)
  )
]


#######################################
### Boxplot
#######################################

gg_Control_Imp <- ggplot(
  Catalonia_Control_Imp,
  aes(
    x = Collection_control_config,
    y = Impurities_percentage_2024
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
    label = anova_label_Control_Imp,
    hjust = 1,
    vjust = 1.2,
    size = 10
  ) +
  add_plot_label(
    label = eta2_label_Control_Imp,
    hjust = 1,
    vjust = 3.2,
    size = 10
  ) +
  add_n_labels(
    y_position = n_label_y_Control_Imp,
    size = 10,
    vjust = 0
  ) +
  add_significance_labels(
    test_results = pairwise_Control_Imp_plot,
    y_positions = significance_y_Control_Imp,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10
  ) +
  scale_y_continuous(
    expand = c(0, 0),
    breaks = seq(
      0,
      y_break_max_Control_Imp,
      by = y_interval_Control_Imp
    )
  ) +
  coord_cartesian(
    ylim = c(
      0,
      y_max_Control_Imp
    )
  ) +
  scale_x_discrete(
    labels = c(
      "Door-to-door | Use control: yes" =
        "Door-to-door\nUse control",
      
      "Door-to-door | Use control: no" =
        "Door-to-door\nNo use control",
      
      "Bring point | Access control: yes" =
        "Bring point\nUse control",
      
      "Bring point | Access control: no" =
        "Bring point\nNo use control"
    )
  ) +
  labs(
    x = "Biowaste collection use control",
    y = "Biowaste impurities [%]"
  ) +
  theme_plot +
  theme(
    axis.text.x = element_text(
      angle = 0
    )
  )

gg_Control_Imp


#######################################
### Save
#######################################

ggsave(
  filename = brit_path(
    "results",
    "figures",
    "Catalonia",
    "Use-access control on biowaste impurities_Catalonia.png"
  ),
  plot = gg_Control_Imp,
  width = 16,
  height = 9,
  dpi = 300
)
