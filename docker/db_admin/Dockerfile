FROM postgis/postgis:12-master

RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip groff less ca-certificates \
    && curl https://cli-assets.heroku.com/install-ubuntu.sh | sh \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install

COPY ./commands/ /usr/bin/