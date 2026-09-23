# Run after setup.R in the supported R environment, including Ubuntu's R 4.3.3.
lock <- renv::lockfile_read("renv.lock")
stopifnot(getRversion() >= "4.3.3")
if (package_version(lock$R$Version) > getRversion()) {
  stop("The lockfile targets a newer R than the supported runtime: ", lock$R$Version)
}
for (name in names(lock$Packages)) {
  expected <- lock$Packages[[name]]$Version
  if (!requireNamespace(name, quietly = TRUE)) stop("Missing package: ", name)
  if (utils::packageVersion(name) != package_version(expected)) {
    stop("Version mismatch for ", name, ": expected ", expected)
  }
}
cat("All locked packages load at their recorded versions on R ", as.character(getRversion()), "\n", sep = "")
