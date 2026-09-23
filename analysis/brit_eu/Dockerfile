FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    r-base=4.3.3-2build2 r-base-dev=4.3.3-2build2 ca-certificates \
    libcurl4-openssl-dev libssl-dev libxml2-dev libfontconfig1-dev \
    libfreetype6-dev libharfbuzz-dev libfribidi-dev libpng-dev libtiff-dev \
    libjpeg-dev libgit2-dev libx11-dev cmake make g++ gfortran pandoc \
    fonts-dejavu-core python3 && rm -rf /var/lib/apt/lists/*
ENV TZ=Etc/UTC LANG=C.UTF-8 LC_ALL=C.UTF-8
RUN Rscript --vanilla -e 'stopifnot(getRversion() == "4.3.3"); install.packages("renv", repos="https://packagemanager.posit.co/cran/2024-04-15")'
WORKDIR /analysis
ENV RENV_PATHS_LIBRARY=/opt/brit-r-library RENV_PATHS_CACHE=/opt/renv-cache R_LIBS_USER=/opt/brit-r-library
RUN mkdir -p /opt/brit-r-library && Rscript --vanilla -e 'options(repos=c(CRAN="https://packagemanager.posit.co/cran/2024-04-15"), Ncpus=2, timeout=300); install.packages(c("tidyverse", "ggpubr", "effectsize", "patchwork", "car", "rstatix", "curl", "jsonlite", "digest"), lib="/opt/brit-r-library", Ncpus=2)'
WORKDIR /opt/brit-r
COPY renv.lock .
COPY tests/test_environment.R tests/test_environment.R
RUN Rscript --vanilla tests/test_environment.R
WORKDIR /analysis
ENTRYPOINT ["Rscript", "--vanilla"]
CMD ["run.R"]
