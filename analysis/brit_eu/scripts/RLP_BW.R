source("R/bootstrap.R")

library(ggpubr)
library(grid)
library(tidyverse)
library(rstatix)
library(car)
library(effectsize)
library(dplyr)
library(ggpubr)
library(purrr)

RLP_BW <- read.csv(brit_path("data", "raw", "RLP_BW", "BRIT_Deutschland_RLP_BW_2024.csv"), 
                      na.strings = "#NV", 
                      header = TRUE, 
                      sep = ";",
                      dec = ".",
                      fileEncoding = "Windows-1252")

###Data organisation
RLP_BW <- RLP_BW %>%
  filter(
    Waste_Category %in% c("Biowaste", "Food waste", "Residual waste")
  ) %>%
  select(
    Catchment,
    Region,
    Mother_region,
    NUTS_LAU,
    Country,
    Collector,
    Collection_System_2024,
    Connection_Rate_2024,
    Waste_Category,
    Fee_System,
    Population_2024,
    Population_Density_2024,
    Quantity_2024
  )

#Spalte für kombiniertes Fee System

Fee_system_combined <- RLP_BW %>%
  filter(
    Waste_Category %in% c("Biowaste", "Residual waste"),
    !is.na(Fee_System)
  ) %>%
  dplyr::select(Catchment, Waste_Category, Fee_System) %>%
  distinct() %>%
  pivot_wider(
    names_from = Waste_Category,
    values_from = Fee_System
  ) %>%
  mutate(
    Fee_System_combined = paste0(
      "BWB: ", ifelse(is.na(`Biowaste`), "NA", `Biowaste`),
      " | RWB: ", ifelse(is.na(`Residual waste`), "NA", `Residual waste`)
    )
  ) %>%
  dplyr::select(Catchment, Fee_System_combined)

RLP_BW <- RLP_BW %>%
  left_join(Fee_system_combined, by = "Catchment") %>%
  relocate(Fee_System_combined, .after = Fee_System)

### Calculate KPI BWRW ratio per municipality / catchment
BWRW_ratios <- RLP_BW %>%
  filter(
    Waste_Category %in% c("Biowaste", "Residual waste"),
    !is.na(Quantity_2024)
  ) %>%
  group_by(NUTS_LAU, Waste_Category) %>%
  summarise(
    Quantity_2024 = sum(Quantity_2024, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  pivot_wider(
    names_from = Waste_Category,
    values_from = Quantity_2024
  ) %>%
  mutate(
    BWRW_ratio = ifelse(
      !is.na(`Biowaste`) &
        !is.na(`Residual waste`) &
        (`Biowaste` + `Residual waste`) > 0,
      (`Biowaste` / (`Biowaste` + `Residual waste`)) * 100,
      NA_real_
    )
  ) %>%
  dplyr::select(NUTS_LAU, BWRW_ratio)

RLP_BW <- RLP_BW %>%
  left_join(BWRW_ratios, by = "NUTS_LAU") %>%
  mutate(
    BWRW_ratio = ifelse(
      Waste_Category %in% c("Biowaste", "Residual waste"),
      BWRW_ratio,
      NA_real_
    )
  ) %>%
  relocate(BWRW_ratio, .after = Quantity_2024)


###Descriptive statistics
##Fee system combination

Fee_system_combi <- RLP_BW %>%
  filter(Waste_Category == "Biowaste",
         !is.na(Fee_System_combined),
         Fee_System_combined != ""
  ) %>%
  distinct(Catchment, Fee_System_combined, Population_2024) %>%
  group_by(Fee_System_combined) %>%
  summarise(
    n_entries = n(),
    population_served = sum(Population_2024, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  mutate(
    share_entries_percent = round(n_entries / sum(n_entries) * 100, 1),
    share_population_percent = round(population_served / sum(population_served) * 100, 1)
  ) %>%
  arrange(desc(n_entries))

###General themes
#boxplot
theme_boxplot <- theme_minimal(base_family = "sans") +
  theme(
    axis.title = element_text(size = 35),
    axis.text = element_text(size = 30),
    axis.title.x = element_text(margin = margin(t = 25)),
    axis.title.y = element_text(margin = margin(r = 25)),
    axis.line = element_line(color = "black", linewidth = 1, linetype = "solid"),
    axis.ticks = element_line(linewidth = 1, color = "black"),
    axis.ticks.length = unit(0.3, "cm"),
    panel.grid.major = element_blank(),
    panel.grid.minor = element_blank()
  ) 

### Fee system

##Descriptive statistics
#Data preparation

Fee_system_analysis <- RLP_BW %>%
  filter(
    Waste_Category == "Biowaste",
    !is.na(Collection_System_2024),
    Collection_System_2024 == "Door to door",
    !is.na(Fee_System_combined),
    Fee_System_combined != "",
    !is.na(BWRW_ratio)
  ) %>%
  distinct(
    Catchment,
    Fee_System_combined,
    BWRW_ratio,
    Population_2024,
    Population_Density_2024
  ) %>%
  mutate(
    Fee_System_combined = as.factor(Fee_System_combined)
  )

#Statistics
Fee_system_descriptives <- Fee_system_analysis %>%
  group_by(Fee_System_combined) %>%
  summarise(
    n = n(),
    min = round(min(BWRW_ratio, na.rm = TRUE), 1),
    q1 = round(quantile(BWRW_ratio, 0.25, na.rm = TRUE), 1),
    median = round(median(BWRW_ratio, na.rm = TRUE), 1),
    mean = round(mean(BWRW_ratio, na.rm = TRUE), 1),
    q3 = round(quantile(BWRW_ratio, 0.75, na.rm = TRUE), 1),
    max = round(max(BWRW_ratio, na.rm = TRUE), 1),
    sd = round(sd(BWRW_ratio, na.rm = TRUE), 1),
    .groups = "drop"
  ) %>%
  arrange(desc(mean))


Fee_system_descriptives

#Pairwise t-test
Fee_system_pairwise_all <- Fee_system_analysis %>%
  pairwise_t_test(
    BWRW_ratio ~ Fee_System_combined,
    p.adjust.method = "bonferroni"
  ) %>%
  arrange(p.adj)

Fee_system_pairwise_all


##Boxplot

#Boxplot dataset
selected_fee_combinations <- c(
  "BWB: Flexible | RWB: Flexible",
  "BWB: No fee | RWB: Flexible",
  "BWB: Flexible | RWB: Pay as you throw (PAYT)",
  "BWB: No fee | RWB: Pay as you throw (PAYT)",
  "BWB: Pay as you throw (PAYT) | RWB: Pay as you throw (PAYT)"
)


Fee_system_boxplot <- Fee_system_analysis %>%
  filter(
    Fee_System_combined %in% selected_fee_combinations,
    !is.na(BWRW_ratio)
  ) %>%
  mutate(
    Fee_System_combined = factor(
      Fee_System_combined,
      levels = selected_fee_combinations
    )
  )



#Boxplot descriptives
Fee_system_boxplot_descriptives <- Fee_system_boxplot %>%
  group_by(Fee_System_combined) %>%
  summarise(
    n = n(),
    min = round(min(BWRW_ratio, na.rm = TRUE), 1),
    q1 = round(quantile(BWRW_ratio, 0.25, na.rm = TRUE), 1),
    median = round(median(BWRW_ratio, na.rm = TRUE), 1),
    mean = round(mean(BWRW_ratio, na.rm = TRUE), 1),
    q3 = round(quantile(BWRW_ratio, 0.75, na.rm = TRUE), 1),
    max = round(max(BWRW_ratio, na.rm = TRUE), 1),
    sd = round(sd(BWRW_ratio, na.rm = TRUE), 1),
    .groups = "drop"
  ) %>%
  arrange(desc(mean))


Fee_system_boxplot_descriptives

#selection for pairwise comparisons
# Pairwise t-tests vorberechnen
pairwise_results_fee <- compare_means(
  BWRW_ratio ~ Fee_System_combined,
  data = Fee_system_boxplot,
  method = "t.test"
)

# Nur signifikante Vergleiche behalten
pairwise_results_fee_sig <- pairwise_results_fee %>%
  filter(p < 0.05)

# Vergleichsliste für stat_compare_means erzeugen
pairwise_comparisons_fee_sig <- pairwise_results_fee_sig %>%
  mutate(
    comparison = map2(group1, group2, c)
  ) %>%
  pull(comparison)

# Dynamische y-Positionen für Signifikanzklammern
label_y_fee_sig <- seq(
  from = 100,
  by = 10,
  length.out = length(pairwise_comparisons_fee_sig)
)

#Boxplot
# Boxplot
gg_FeeSystem_BWRW <- ggplot(
  Fee_system_boxplot,
  aes(x = Fee_System_combined, y = BWRW_ratio)
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
  stat_summary(
    fun.data = \(x) data.frame(
      y = 70,
      label = paste0("n = ", sum(!is.na(x)))
    ),
    geom = "text",
    size = 10,
    vjust = 0
  ) +
  stat_compare_means(
    method = "anova",
    label.x = Inf,
    label.y = Inf,
    hjust = 1.05,
    vjust = 1.5,
    size = 10
  ) +
  stat_compare_means(
    comparisons = pairwise_comparisons_fee_sig,
    label = "p.signif",
    method = "t.test",
    label.y = c(80, 95, 90, 85),
    size = 10,
    textsize = 0,
    hide.ns = TRUE
  ) +
  scale_y_continuous(
    limits = c(0, 115),
    expand = c(0, 0),
    breaks = seq(0, 100, 20)
  ) +
  labs(
    x = "Fee system combination",
    y = "Total Separation Rate [%]"
  ) +
  theme_boxplot +
  scale_x_discrete(
    labels = c(
      "BWB: Flexible | RWB: Flexible" =
        "BWB: Flexible\nRWB: Flexible",
      "BWB: No fee | RWB: Flexible" =
        "BWB: No fee\nRWB: Flexible",
      "BWB: Pay as you throw (PAYT) | RWB: Pay as you throw (PAYT)" =
        "BWB: PAYT\nRWB: PAYT",
      "BWB: Flexible | RWB: Pay as you throw (PAYT)" =
        "BWB: Flexible\nRWB: PAYT",
      "BWB: No fee | RWB: Pay as you throw (PAYT)" =
        "BWB: No fee\nRWB: PAYT"
    )
  )

gg_FeeSystem_BWRW


ggsave(filename = brit_path("results", "figures", "RLP_BW", "Fee system combination_SR BWB-RWB.png"), 
       plot = gg_FeeSystem_BWRW, width = 16, height = 9, dpi = 300)


# ANOVA
anova_model_fee <- aov(
  BWRW_ratio ~ Fee_System_combined,
  data = Fee_system_boxplot
)

summary(anova_model_fee)

# Levene test
leveneTest(
  BWRW_ratio ~ Fee_System_combined,
  data = Fee_system_boxplot
)

# Welch ANOVA
welch_anova_fee <- oneway.test(
  BWRW_ratio ~ Fee_System_combined,
  data = Fee_system_boxplot,
  var.equal = FALSE
)

welch_anova_fee

# Effect size
anova_model_fee <- aov(
  BWRW_ratio ~ Fee_System_combined,
  data = Fee_system_boxplot
)

eta_squared(anova_model_fee)
omega_squared(anova_model_fee)

