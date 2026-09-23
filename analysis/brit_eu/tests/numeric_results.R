# Export comparable statistical summaries without serializing ggplot internals.
# Rscript --vanilla tests/numeric_results.R results/objects /tmp/numeric.rds
args <- commandArgs(TRUE)
stopifnot(length(args) == 2L)
plain <- function(x, depth = 0L) {
  if (depth > 5L || is.function(x) || is.environment(x)) return(NULL)
  if (inherits(x, "lm")) return(list(coefficients = unname(coef(x)), residual_df = x$df.residual))
  if (inherits(x, "htest")) return(lapply(x[intersect(names(x), c("statistic", "parameter", "p.value", "estimate", "conf.int"))], as.numeric))
  if (is.data.frame(x)) return(lapply(x, function(v) if (is.factor(v)) as.character(v) else unname(v)))
  if (is.list(x)) return(lapply(x, plain, depth = depth + 1L))
  if (is.atomic(x)) return(unname(x))
  NULL
}
result <- list()
for (file in list.files(args[1], pattern = "\\.rds$", full.names = TRUE)) {
  objects <- readRDS(file)
  selected <- grep("summary|stat|test|anova|cor|cohen|effect|descript|model", names(objects), value = TRUE, ignore.case = TRUE)
  selected <- selected[!vapply(objects[selected], function(x) is.function(x) || inherits(x, c("ggplot", "theme")), logical(1))]
  result[[basename(file)]] <- lapply(objects[selected], plain)
}
saveRDS(result, args[2], version = 2)
cat("Exported ", sum(lengths(result)), " statistical objects\n", sep = "")
