# Inspect the limited p-value differences between the R 4.6 and R 4.3 runs.
args <- commandArgs(TRUE)
stopifnot(length(args) == 2L)
old <- readRDS(args[1])
new <- readRDS(args[2])
rows <- list()
for (case in names(old)) {
  for (name in names(old[[case]])) {
    a <- old[[case]][[name]]
    b <- new[[case]][[name]]
    if (!is.list(a) || !is.list(b)) next
    for (field in intersect(c("p", "p.adj"), intersect(names(a), names(b)))) {
      x <- a[[field]]
      y <- b[[field]]
      if (!is.numeric(x) || !is.numeric(y) || length(x) != length(y)) next
      for (i in which(!is.na(x) & !is.na(y) & abs(x - y) > 1e-8)) {
        rows[[length(rows) + 1L]] <- data.frame(
          case = case, object = name, field = field, row = i,
          old = x[i], new = y[i], absolute_difference = abs(x[i] - y[i]),
          decision_changed = (x[i] < 0.05) != (y[i] < 0.05)
        )
      }
    }
  }
}
report <- if (length(rows)) do.call(rbind, rows) else data.frame()
print(report, row.names = FALSE, digits = 8)
if (nrow(report)) {
  cat("Maximum absolute p-value difference:", max(report$absolute_difference), "\n")
  cat("Changed significance decisions:", sum(report$decision_changed), "\n")
}
