FROM ubuntu:bionic

ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="Europe/Berlin"

RUN apt-get update && apt-get install -y \
    python3 python3-pip libpq-dev postgresql postgresql-contrib binutils libproj-dev gdal-bin nginx curl

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y locales \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8

RUN ln -s /usr/bin/python3 /usr/bin/python && \
    ln -s /usr/bin/pip3 /usr/bin/pip

WORKDIR /var/www/flexibi_dst
COPY ./requirements.txt .
RUN pip install --upgrade pip && pip install -r ./requirements.txt

COPY . /var/www/flexibi_dst
EXPOSE 8000

COPY ./entrypoint.sh /var/www/flexibi_dst/entrypoint.sh
#ENTRYPOINT /app/entrypoint.sh

CMD ["sh", "/var/www/flexibi_dst/entrypoint.sh"]