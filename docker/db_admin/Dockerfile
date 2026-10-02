# ------------------------------------------------------------
# db_admin Docker image
# Postgres 15 client tools + admin CLIs (Heroku & AWS)
#
# Postgres 15 matches the Heroku add-on version; the postgis base
# images still ship EOL Debian bullseye with a dead apt repo, so we
# build on the maintained official postgres image instead. The admin
# commands only need pg client tools — PostGIS lives in the db image.
# ------------------------------------------------------------

FROM postgres:15-trixie

ENV DEBIAN_FRONTEND=noninteractive

# ------------------------------------------------------------------
# 1. Install required OS packages
# ------------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    groff \
    less \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------
# 2. Install Heroku CLI via tarball
# -------------------------------------------------------------
ENV HEROKU_CLI_VERSION="latest"
RUN curl -fsSL https://cli-assets.heroku.com/heroku-linux-x64.tar.gz -o /tmp/heroku.tar.gz \
    && mkdir -p /usr/local/lib \
    && tar -xzf /tmp/heroku.tar.gz -C /usr/local/lib \
    && ln -s /usr/local/lib/heroku/bin/heroku /usr/local/bin/heroku \
    && rm /tmp/heroku.tar.gz

# ---------------------------------------------
# 3. Install AWS CLI v2
# ---------------------------------------------
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip


# ------------------------------------------------------------------
# 4. Make custom commands executable
# ------------------------------------------------------------------
COPY ./commands/ /usr/bin/
RUN chmod +x /usr/bin/dump /usr/bin/pull /usr/bin/push