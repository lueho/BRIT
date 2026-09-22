############################################################################################
### Statistics helpers
############################################################################################


#######################################
## Significance formatting
#######################################

get_significance <- function(p) {
  dplyr::case_when(
    is.na(p)   ~ NA_character_,
    p <= 0.0001 ~ "****",
    p <= 0.001  ~ "***",
    p <= 0.01   ~ "**",
    p <= 0.05   ~ "*",
    TRUE        ~ "ns"
  )
}


format_p_value <- function(p, digits = 2) {
  dplyr::case_when(
    is.na(p)    ~ "p = NA",
    p <= 0.0001 ~ "p < 0.0001",
    p <= 0.001  ~ "p < 0.001",
    p <= 0.01   ~ "p < 0.01",
    p <= 0.05   ~ "p < 0.05",
    TRUE        ~ paste0("p = ", signif(p, digits))
  )
}



#########################################
### ANOVA formatting
#########################################

format_anova_label <- function(
    p,
    method = NULL,
    show_method = FALSE,
    show_significance = FALSE
) {
  
  label_method <- if (
    show_method && !is.null(method)
  ) {
    method
  } else {
    "ANOVA"
  }
  
  label <- paste0(
    label_method,
    ": ",
    format_p_value(p)
  )
  
  if (show_significance) {
    label <- paste0(
      label,
      " (",
      get_significance(p),
      ")"
    )
  }
  
  label
}



#######################################
## Descriptive summary
#######################################

safe_summary_value <- function(
    x,
    fun,
    digits = 2,
    min_n = 1,
    ...
) {
  x <- x[!is.na(x)]
  
  if (length(x) < min_n) {
    return(NA_real_)
  }
  
  round(
    unname(fun(x, ...)),
    digits
  )
}


summary_statistics <- function(
    data,
    summary_var,
    group_var = NULL,
    digits = 2
) {
  
  if (!is.null(group_var)) {
    data <- data %>%
      group_by(
        across(all_of(group_var))
      )
  }
  
  data %>%
    summarise(
      n = sum(!is.na(.data[[summary_var]])),
      min = safe_summary_value(
        .data[[summary_var]],
        min,
        digits = digits
      ),
      q1 = safe_summary_value(
        .data[[summary_var]],
        quantile,
        digits = digits,
        probs = 0.25
      ),
      median = safe_summary_value(
        .data[[summary_var]],
        median,
        digits = digits
      ),
      mean = safe_summary_value(
        .data[[summary_var]],
        mean,
        digits = digits
      ),
      q3 = safe_summary_value(
        .data[[summary_var]],
        quantile,
        digits = digits,
        probs = 0.75
      ),
      max = safe_summary_value(
        .data[[summary_var]],
        max,
        digits = digits
      ),
      sd = safe_summary_value(
        .data[[summary_var]],
        sd,
        digits = digits,
        min_n = 2
      ),
      .groups = "drop"
    )
}


#######################################
## Population distribution
#######################################

summarise_population_distribution <- function(
    data,
    category_var,
    area_var = "NUTS_LAU",
    population_var = "Population_2024",
    density_var = NULL,
    density_digits = 1,
    sort_by = c("entries_desc", "category")
) {
  sort_by <- match.arg(sort_by)
  
  distinct_vars <- c(
    area_var,
    category_var,
    population_var,
    density_var
  )
  
  base_data <- data %>%
    distinct(
      across(all_of(distinct_vars))
    )
  
  result <- base_data %>%
    group_by(
      across(all_of(category_var))
    ) %>%
    summarise(
      n_entries = n(),
      population_served = sum(
        .data[[population_var]],
        na.rm = TRUE
      ),
      .groups = "drop"
    )
  
  if (!is.null(density_var)) {
    result <- result %>%
      left_join(
        base_data %>%
          group_by(
            across(all_of(category_var))
          ) %>%
          summarise(
            mean_population_density = round(
              mean(.data[[density_var]], na.rm = TRUE),
              density_digits
            ),
            sd_population_density = round(
              sd(.data[[density_var]], na.rm = TRUE),
              density_digits
            ),
            .groups = "drop"
          ),
        by = category_var
      )
  }
  
  result <- result %>%
    mutate(
      share_entries_percent = round(
        n_entries / sum(n_entries) * 100,
        1
      ),
      share_population_percent = if (
        sum(population_served) > 0
      ) {
        round(
          population_served /
            sum(population_served) *
            100,
          1
        )
      } else {
        NA_real_
      }
    )
  
  if (sort_by == "category") {
    result %>%
      arrange(
        across(all_of(category_var))
      )
  } else {
    result %>%
      arrange(desc(n_entries))
  }
}






#######################################
## One-way ANOVA / Welch ANOVA
#######################################

run_oneway_test <- function(
    data,
    response,
    group,
    center = median
) {
  test_data <- data %>%
    filter(
      !is.na(.data[[response]]),
      !is.na(.data[[group]])
    )
  
  test_data[[group]] <- droplevels(
    factor(test_data[[group]])
  )
  
  group_sizes <- table(
    test_data[[group]]
  )
  
  if (length(group_sizes) < 2) {
    stop(
      "The test requires at least two groups."
    )
  }
  
  if (any(group_sizes < 2)) {
    stop(
      "Each group requires at least two observations."
    )
  }
  
  test_formula <- reformulate(
    group,
    response
  )
  
  levene_result <- car::leveneTest(
    test_formula,
    data = test_data,
    center = center
  )
  
  levene_p <- levene_result[
    1,
    "Pr(>F)"
  ]
  
  if (is.na(levene_p)) {
    stop(
      "Levene's test did not return a valid p-value."
    )
  }
  
  # Always generated for effect-size calculation
  anova_model <- aov(
    test_formula,
    data = test_data
  )
  
  if (levene_p >= 0.05) {
    
    anova_result <- summary(
      anova_model
    )
    
    anova_method <- "Classical one-way ANOVA"
    
    anova_p <- anova_result[[1]][["Pr(>F)"]][1]
    
  } else {
    
    anova_result <- rstatix::welch_anova_test(
      test_data,
      test_formula
    )
    
    anova_method <- "Welch ANOVA"
    anova_p <- anova_result$p[1]
  }
  
  list(
    data = test_data,
    levene_result = levene_result,
    levene_p = levene_p,
    anova_model = anova_model,
    anova_result = anova_result,
    anova_method = anova_method,
    anova_p = anova_p
  )
}



#######################################
## Pairwise t-test
#######################################

run_pairwise_t_test <- function(
    data,
    response,
    group,
    p_adjust = "bonferroni",
    pool_sd = FALSE
) {
  test_data <- data %>%
    filter(
      !is.na(.data[[response]]),
      !is.na(.data[[group]])
    )
  
  group_sizes <- table(
    test_data[[group]]
  )
  
  if (length(group_sizes) < 2) {
    stop(
      "The test requires at least two groups."
    )
  }
  
  if (any(group_sizes < 2)) {
    stop(
      "Each group requires at least two observations."
    )
  }
  
  rstatix::pairwise_t_test(
    test_data,
    reformulate(group, response),
    p.adjust.method = p_adjust,
    pool.sd = pool_sd
  )
}


##################################################################################
## Scatter plot regression statistics // Linear correlation and regression
##################################################################################

run_scatter_lm_test <- function(
    data,
    x,
    y,
    digits = 2
) {
  
  test_data <- data %>%
    filter(
      !is.na(.data[[x]]),
      !is.na(.data[[y]])
    )
  
  if (nrow(test_data) < 3) {
    stop(
      "At least three complete observations are required."
    )
  }
  
  if (
    n_distinct(test_data[[x]]) < 2 ||
    n_distinct(test_data[[y]]) < 2
  ) {
    stop(
      "Both x and y require at least two distinct values."
    )
  }
  
  cor_result <- cor.test(
    test_data[[x]],
    test_data[[y]],
    method = "pearson"
  )
  
  lm_model <- lm(
    reformulate(x, y),
    data = test_data
  )
  
  intercept <- coef(lm_model)[1]
  slope <- coef(lm_model)[2]
  
  labels <- c(
    paste0(
      "Pearson r = ",
      round(unname(cor_result$estimate), digits),
      "; ",
      format_p_value(cor_result$p.value)
    ),
    paste0(
      "R² = ",
      round(summary(lm_model)$r.squared, digits)
    ),
    paste0(
      "y = ",
      round(slope, digits),
      "x ",
      ifelse(intercept >= 0, "+ ", "- "),
      abs(round(intercept, digits))
    )
  )
  
  list(
    data = test_data,
    cor_result = cor_result,
    lm_model = lm_model,
    slope = slope,
    intercept = intercept,
    labels = labels
  )
}











#####################################################################################################################################################################
### Plotting helpers
#####################################################################################################################################################################

##############################
### General plot theme
##############################

theme_plot <- theme_minimal(
  base_family = "sans"
) +
  theme(
    axis.title = element_text(size = 35),
    axis.text = element_text(size = 30),
    axis.title.x = element_text(
      margin = margin(t = 25)
    ),
    axis.title.y = element_text(
      margin = margin(r = 25)
    ),
    axis.line = element_line(
      color = "black",
      linewidth = 1,
      linetype = "solid"
    ),
    axis.ticks = element_line(
      linewidth = 1,
      color = "black"
    ),
    axis.ticks.length = unit(0.3, "cm"),
    panel.grid.major = element_blank(),
    panel.grid.minor = element_blank()
  )



#################################################################################
### y-axis helpers
#################################################################################

#######################################
## Y-axis preparation: quantity values
#######################################

prepare_y_axis_quantity <- function(
    data,
    value_var,
    interval,
    n_significance = 0,
    n_label_offset = 0.5,
    significance_start_offset = 1.5,
    significance_step_offset = 1,
    top_offset = 1
) {
  
  data_max <- max(
    data[[value_var]],
    na.rm = TRUE
  )
  
  n_label_y <- data_max +
    interval * n_label_offset
  
  if (n_significance > 0) {
    significance_y_positions <- data_max +
      interval *
      (
        significance_start_offset +
          significance_step_offset * seq(0, n_significance - 1)
      )
  } else {
    significance_y_positions <- numeric(0)
  }
  
  y_needed <- max(
    c(
      data_max,
      n_label_y,
      significance_y_positions
    ),
    na.rm = TRUE
  ) +
    interval * top_offset
  
  y_break_max <- ceiling(
    y_needed / interval
  ) *
    interval
  
  y_max <- y_break_max +
    interval * 0.10
  
  list(
    interval = interval,
    data_max = data_max,
    n_label_y = n_label_y,
    significance_y_positions = significance_y_positions,
    break_max = y_break_max,
    y_max = y_max
  )
}



#######################################
## Y-axis preparation: quantity values
## with compact significance brackets
#######################################

prepare_y_axis_quantity_compact_significance <- function(
    data,
    value_var,
    interval,
    test_results,
    group_levels,
    n_label_offset = 0.5,
    significance_start_offset = 1.5,
    significance_step_offset = 1,
    top_offset = 1,
    group1_col = "group1",
    group2_col = "group2"
) {
  
  data_max <- max(
    data[[value_var]],
    na.rm = TRUE
  )
  
  n_label_y <- data_max +
    interval * n_label_offset
  
  if (nrow(test_results) == 0) {
    
    significance_y_positions <- numeric(0)
    
  } else {
    
    group_positions <- seq_along(group_levels)
    names(group_positions) <- group_levels
    
    brackets <- test_results %>%
      mutate(
        original_row = row_number(),
        x1 = group_positions[.data[[group1_col]]],
        x2 = group_positions[.data[[group2_col]]],
        xmin = pmin(x1, x2),
        xmax = pmax(x1, x2),
        span = xmax - xmin
      ) %>%
      arrange(
        span,
        xmin,
        xmax
      )
    
    layers <- integer(
      nrow(brackets)
    )
    
    occupied <- list()
    
    for (i in seq_len(nrow(brackets))) {
      
      current_min <- brackets$xmin[i]
      current_max <- brackets$xmax[i]
      
      layer <- 1
      
      repeat {
        
        if (
          length(occupied) < layer ||
          is.null(occupied[[layer]])
        ) {
          occupied[[layer]] <- data.frame(
            xmin = numeric(0),
            xmax = numeric(0)
          )
        }
        
        # Strict overlap:
        # Brackets sharing only one endpoint are allowed
        overlaps <- occupied[[layer]] %>%
          filter(
            xmin < current_max,
            xmax > current_min
          )
        
        if (nrow(overlaps) == 0) {
          break
        }
        
        layer <- layer + 1
      }
      
      layers[i] <- layer
      
      occupied[[layer]] <- bind_rows(
        occupied[[layer]],
        data.frame(
          xmin = current_min,
          xmax = current_max
        )
      )
    }
    
    brackets <- brackets %>%
      mutate(
        layer = layers,
        y.position = data_max +
          interval *
          (
            significance_start_offset +
              significance_step_offset * (layer - 1)
          )
      )
    
    significance_y_positions <- brackets %>%
      arrange(original_row) %>%
      pull(y.position)
  }
  
  y_needed <- max(
    c(
      data_max,
      n_label_y,
      significance_y_positions
    ),
    na.rm = TRUE
  ) +
    interval * top_offset
  
  y_break_max <- ceiling(
    y_needed / interval
  ) *
    interval
  
  y_max <- y_break_max +
    interval * 0.10
  
  list(
    interval = interval,
    data_max = data_max,
    n_label_y = n_label_y,
    significance_y_positions = significance_y_positions,
    break_max = y_break_max,
    y_max = y_max
  )
}


#######################################
## Y-axis preparation: percentage values
## with optional compact significance brackets
#######################################

prepare_y_axis_percent <- function(
    data,
    value_var,
    interval = 10,
    max_break = 100,
    min_break_max = NULL,
    test_results = NULL,
    group_levels = NULL,
    n_label_offset = 0.5,
    significance_start_offset = 1.5,
    significance_step_offset = 1,
    top_offset = .5,
    y_max_padding = 2,
    group1_col = "group1",
    group2_col = "group2"
) {
  
  data_max <- max(
    data[[value_var]],
    na.rm = TRUE
  )
  
  n_label_y <- data_max +
    interval * n_label_offset
  
  if (
    is.null(test_results) ||
    nrow(test_results) == 0
  ) {
    
    significance_y_positions <- numeric(0)
    
  } else {
    
    if (is.null(group_levels)) {
      stop(
        "group_levels must be provided when test_results are used."
      )
    }
    
    group_positions <- seq_along(group_levels)
    names(group_positions) <- group_levels
    
    brackets <- test_results %>%
      mutate(
        original_row = row_number(),
        x1 = group_positions[.data[[group1_col]]],
        x2 = group_positions[.data[[group2_col]]],
        xmin = pmin(x1, x2),
        xmax = pmax(x1, x2),
        span = xmax - xmin
      ) %>%
      arrange(
        span,
        xmin,
        xmax
      )
    
    layers <- integer(
      nrow(brackets)
    )
    
    occupied <- list()
    
    for (i in seq_len(nrow(brackets))) {
      
      current_min <- brackets$xmin[i]
      current_max <- brackets$xmax[i]
      
      layer <- 1
      
      repeat {
        
        if (
          length(occupied) < layer ||
          is.null(occupied[[layer]])
        ) {
          occupied[[layer]] <- data.frame(
            xmin = numeric(0),
            xmax = numeric(0)
          )
        }
        
        # Strict overlap:
        # Brackets sharing only one endpoint are allowed
        overlaps <- occupied[[layer]] %>%
          filter(
            xmin < current_max,
            xmax > current_min
          )
        
        if (nrow(overlaps) == 0) {
          break
        }
        
        layer <- layer + 1
      }
      
      layers[i] <- layer
      
      occupied[[layer]] <- bind_rows(
        occupied[[layer]],
        data.frame(
          xmin = current_min,
          xmax = current_max
        )
      )
    }
    
    brackets <- brackets %>%
      mutate(
        layer = layers,
        y.position = data_max +
          interval *
          (
            significance_start_offset +
              significance_step_offset * (layer - 1)
          )
      )
    
    significance_y_positions <- brackets %>%
      arrange(original_row) %>%
      pull(y.position)
  }
  
  y_needed <- max(
    c(
      data_max,
      n_label_y,
      significance_y_positions
    ),
    na.rm = TRUE
  ) +
    interval * top_offset
  
  y_break_max <- ceiling(
    y_needed / interval
  ) *
    interval
  
  y_break_max <- min(
    y_break_max,
    max_break
  )
  
  if (!is.null(min_break_max)) {
    y_break_max <- max(
      y_break_max,
      min_break_max
    )
  }
  
  y_max <- max(
    y_needed,
    y_break_max
  )
  
  y_max <- ceiling(
    y_max / interval
  ) *
    interval
  
  y_max <- y_max + y_max_padding
  
  list(
    interval = interval,
    data_max = data_max,
    n_label_y = n_label_y,
    significance_y_positions = significance_y_positions,
    break_max = y_break_max,
    y_max = y_max
  )
}










#######################################
## Add significance labels
#######################################

add_significance_labels <- function(
    test_results,
    y_positions,
    label = "p.adj.signif",
    tip.length = 0.01,
    size = 10,
    ...
) {
  
  if (nrow(test_results) == 0) {
    return(NULL)
  }
  
  if (length(y_positions) < nrow(test_results)) {
    stop(
      "Not enough y_positions: ",
      nrow(test_results),
      " position(s) required, but only ",
      length(y_positions),
      " provided."
    )
  }
  
  test_results %>%
    mutate(
      y.position = y_positions[seq_len(n())]
    ) %>%
    ggpubr::stat_pvalue_manual(
      label = label,
      y.position = "y.position",
      tip.length = tip.length,
      size = size,
      ...
    )
}


#######################################
## Add sample-size labels
#######################################

add_n_labels <- function(
    y_position,
    size = 10,
    vjust = 0,
    prefix = "n = "
) {
  
  ggplot2::stat_summary(
    fun.data = function(x) {
      data.frame(
        y = y_position,
        label = paste0(
          prefix,
          sum(!is.na(x))
        )
      )
    },
    geom = "text",
    size = size,
    vjust = vjust
  )
}



#######################################
## Add plot annotation
#######################################

add_plot_label <- function(
    label,
    x = Inf,
    y = Inf,
    hjust = 1.0,
    vjust = 1.2,
    size = 10
) {
  
  ggplot2::annotate(
    "text",
    x = x,
    y = y,
    label = label,
    hjust = hjust,
    vjust = vjust,
    size = size
  )
}



#######################################
## Add scatter plot model labels
#######################################

add_scatter_lm_labels <- function(
    labels,
    slope = NULL,
    position = c("auto", "left", "right"),
    x_left = 5,
    x_right = Inf,
    y = Inf,
    vjust_start = 2,
    vjust_step = 2,
    size = 10
) {
  
  position <- match.arg(position)
  
  if (position == "auto") {
    
    if (is.null(slope)) {
      stop(
        "For position = 'auto', slope must be provided."
      )
    }
    
    position <- ifelse(
      unname(slope) >= 0,
      "left",
      "right"
    )
  }
  
  labels <- labels %>%
    as.character() %>%
    unname() %>%
    trimws()
  
  x_position <- if (
    position == "left"
  ) {
    x_left
  } else {
    x_right
  }
  
  hjust_value <- if (
    position == "left"
  ) {
    0
  } else {
    1
  }
  
  label_data <- tibble::tibble(
    x = rep(
      x_position,
      length(labels)
    ),
    y = rep(
      y,
      length(labels)
    ),
    label = labels,
    hjust = rep(
      hjust_value,
      length(labels)
    ),
    vjust = seq(
      vjust_start,
      by = vjust_step,
      length.out = length(labels)
    )
  )
  
  ggplot2::geom_text(
    data = label_data,
    mapping = ggplot2::aes(
      x = x,
      y = y,
      label = label,
      hjust = hjust,
      vjust = vjust
    ),
    inherit.aes = FALSE,
    size = size
  )
}










################################################################################################
### Validation helpers
################################################################################################

