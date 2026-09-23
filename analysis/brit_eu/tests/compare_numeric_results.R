# Rscript --vanilla tests/compare_numeric_results.R reference.rds current.rds
args <- commandArgs(TRUE)
stopifnot(length(args) == 2L)
reference <- readRDS(args[1])
current <- readRDS(args[2])
stopifnot(identical(names(reference), names(current)))
differences <- character()
p_differences <- numeric()
for (case in names(reference)) {
  old <- reference[[case]]
  new <- current[[case]]
  if (!identical(names(old), names(new))) {
    differences <- c(differences, paste(case, "object names changed"))
    next
  }
  for (name in names(old)) {
    a <- old[[name]]
    b <- new[[name]]
    if (is.list(a) && is.list(b)) {
      for (field in intersect(c("p", "p.adj"), intersect(names(a), names(b)))) {
        x <- a[[field]]
        y <- b[[field]]
        if (!is.numeric(x) || !is.numeric(y) || length(x) != length(y) ||
            !identical(is.na(x), is.na(y))) next
        gap <- abs(x - y)
        p_differences <- c(p_differences, gap[!is.na(gap)])
        if (any(gap > 0.0005, na.rm = TRUE) ||
            any((x < 0.05) != (y < 0.05), na.rm = TRUE)) {
          differences <- c(differences, paste(case, name, field, "p-value or significance decision changed"))
        }
        a[[field]] <- NULL
        b[[field]] <- NULL
      }
    }
    result <- all.equal(a, b, tolerance = 1e-8, check.attributes = FALSE)
    if (!isTRUE(result)) differences <- c(differences, paste(case, name, paste(result, collapse = "; ")))
  }
}
if (length(differences)) {
  writeLines(differences)
  stop(length(differences), " statistical objects differ")
}
cat("All ", sum(lengths(reference)), " selected statistical objects match within 1e-8, ",
    "except p-values with maximum absolute difference ", max(p_differences, 0),
    " (allowed <= 0.0005; no 5% significance decision changed)\n", sep = "")
