# Fixed project analyses: Rscript run.R [--case=nrw|rlp|sweden|south_tyrol|rlp_bw|catalonia]
args_full <- commandArgs(FALSE)
script <- grep("^--file=", args_full, value = TRUE)
if (length(script)) setwd(dirname(normalizePath(sub("^--file=", "", script[1]))))
options(brit.root = normalizePath(getwd()), warn = 1)
if (nzchar(Sys.getenv("RENV_PATHS_LIBRARY"))) .libPaths(c(Sys.getenv("RENV_PATHS_LIBRARY"), .libPaths()))
if (!requireNamespace("ggpubr", quietly = TRUE)) stop("Run setup.R first, or use the supplied Docker image.")
source("R/bootstrap.R")
args <- commandArgs(TRUE)
options(brit.catalonia.rebuild = "--rebuild-catalonia" %in% args)
chosen <- sub("^--case=", "", grep("^--case=", args, value = TRUE))
scripts <- c(nrw = "NRW.R", rlp = "RLP.R", sweden = "Sweden.R", south_tyrol = "South Tyrol.R",
             rlp_bw = "RLP_BW.R", catalonia = "Catalonia.R")
if (length(chosen)) {
  if (length(chosen) != 1L || !chosen %in% names(scripts)) stop("Unknown --case; see README.md")
  scripts <- scripts[chosen]
}
provenance <- brit_verify_inputs("--allow-custom-data" %in% args)
code_files <- c("run.R", "renv.lock", list.files("R", full.names = TRUE), list.files("scripts", full.names = TRUE))
provenance$code_sha256 <- setNames(lapply(code_files, function(path) digest::digest(file = path, algo = "sha256")), code_files)
provenance$catalonia_input <- if (getOption("brit.catalonia.rebuild")) "rebuilt_from_raw" else "archived_analysis_input"
dir.create("results/logs", recursive = TRUE, showWarnings = FALSE)
dir.create("results/objects", recursive = TRUE, showWarnings = FALSE)
writeLines(capture.output(sessionInfo()), "results/session-info.txt")
jsonlite::write_json(provenance, "results/input-provenance.json", auto_unbox = TRUE, pretty = TRUE)
set.seed(2024)
if ("catalonia" %in% names(scripts)) {
  scripts <- append(scripts, c(catalonia_preparation = "Catalonia_Impropis_Derivationandsummary.R"),
                    after = match("catalonia", names(scripts)) - 1L)
}
for (case in names(scripts)) {
  message("Running ", case, " ...")
  env <- new.env(parent = globalenv())
  log <- file(file.path("results/logs", paste0(case, ".txt")), open = "wt")
  grDevices::cairo_pdf(file.path("results/figures", paste0(case, "-plots.pdf")), width = 12, height = 8)
  sink(log); sink(log, type = "message")
  result <- tryCatch({
    source(file.path("scripts", scripts[[case]]), local = env, print.eval = TRUE)
    saveRDS(as.list(env, all.names = TRUE), file.path("results/objects", paste0(case, ".rds")))
    NULL
  }, error = identity, finally = {
    sink(type = "message"); sink(); close(log); grDevices::dev.off()
  })
  if (inherits(result, "error")) stop(case, " failed: ", conditionMessage(result), "; see results/logs/", case, ".txt")
  rm(env); gc(verbose = FALSE)
}
writeLines(capture.output(sessionInfo()), "results/session-info.txt")
message("Complete. Figures, console results, analysis objects and provenance are in results/.")
