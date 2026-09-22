# Rscript live.R: download and freeze current BRIT data, then run a simple editable summary.
args_full <- commandArgs(FALSE)
script <- grep("^--file=", args_full, value = TRUE)
if (length(script)) setwd(dirname(normalizePath(sub("^--file=", "", script[1]))))
if (nzchar(Sys.getenv("RENV_PATHS_LIBRARY"))) .libPaths(c(Sys.getenv("RENV_PATHS_LIBRARY"), .libPaths()))
source("R/brit_api.R")
# Edit filters for your question. IDs are the IDs used in the BRIT interface.
# Example: list(scope = "published", catchment = 123, valid_on = "2024-12-31")
# valid_on selects the collection version; it does not select the year of a metric.
filters <- list(scope = "published")
collections <- brit_collections(filters = filters)
dir.create("results/live", recursive = TRUE, showWarnings = FALSE)
stamp <- format(Sys.time(), "%Y%m%dT%H%M%SZ", tz = "UTC")
path <- file.path("results/live", paste0("collections-", stamp, ".rds"))
brit_save_snapshot(collections, path)
utils::write.csv(collections, sub("rds$", "csv", path), row.names = FALSE, na = "", fileEncoding = "UTF-8")
if (nrow(collections)) {
  summary <- dplyr::count(collections, country, waste_category, name = "collections")
  print(summary)
  utils::write.csv(summary, "results/live/summary.csv", row.names = FALSE, fileEncoding = "UTF-8")
}
message("Saved live snapshot: ", path)
