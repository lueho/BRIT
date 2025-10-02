# ------------------------------------------------------------
# db_admin Docker image
# PostGIS 15 + admin CLIs (Heroku & AWS) with minimal footprint
# ------------------------------------------------------------

FROM postgis/postgis:15-3.4

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