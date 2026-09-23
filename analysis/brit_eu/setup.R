# Rscript --vanilla setup.R; alternatively source("setup.R") in the project.
args <- commandArgs(FALSE)
script <- grep("^--file=", args, value = TRUE)
if (length(script)) setwd(dirname(normalizePath(sub("^--file=", "", script[1]))))
if (getRversion() < "4.3.3") stop("This analysis package requires R >= 4.3.3 (Ubuntu 24.04 ships R 4.3.3).")
if (!identical(as.character(getRversion()), "4.3.3")) {
  warning("This release was tested with R 4.3.3. Use the supplied Dockerfile for the validated runtime.")
}
options(renv.config.auto.snapshot = FALSE)
source("renv/activate.R")
renv::restore(prompt = FALSE)
source("tests/test_environment.R")
cat("Ready. Run Rscript run.R or source('run.R').\n")
