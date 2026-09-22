# Rscript --vanilla setup.R; alternatively source("setup.R") in the project.
args <- commandArgs(FALSE)
script <- grep("^--file=", args, value = TRUE)
if (length(script)) setwd(dirname(normalizePath(sub("^--file=", "", script[1]))))
if (!identical(as.character(getRversion()), "4.6.1")) {
  warning("The original environment uses R 4.6.1. Use the supplied Dockerfile for an exact runtime.")
}
options(renv.config.auto.snapshot = FALSE)
source("renv/activate.R")
renv::restore(prompt = FALSE)
cat("Ready. Run Rscript run.R or source('run.R').\n")
