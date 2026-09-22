FROM rocker/r-ver:4.6.1@sha256:4e6e6696ff54a86625c7f80046478e67014a2184e942b85eeff43db7b992d93e
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev libssl-dev libxml2-dev libfontconfig1-dev \
    libfreetype6-dev libharfbuzz-dev libfribidi-dev libpng-dev libtiff-dev \
    libjpeg-dev libgit2-dev cmake make g++ gfortran && rm -rf /var/lib/apt/lists/*
ENV RENV_PATHS_LIBRARY=/opt/brit-r-library RENV_PATHS_CACHE=/opt/renv-cache
WORKDIR /opt/brit-r
COPY renv.lock .
RUN Rscript --vanilla -e 'options(repos=c(CRAN="https://p3m.dev/cran/__linux__/noble/latest"), Ncpus=2); install.packages("renv"); renv::restore(project="/opt/brit-r", prompt=FALSE)'
ENV R_LIBS_USER=/opt/brit-r-library
WORKDIR /analysis
ENTRYPOINT ["Rscript", "--vanilla"]
CMD ["run.R"]
