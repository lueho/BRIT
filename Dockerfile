ARG HOST_ENVIRONMENT=prod

FROM python:3.7 as prod

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
    && apt-get install -y --fix-missing binutils libproj-dev gdal-bin

FROM prod as dev

RUN apt-get update \
    && apt-get install -y --fix-missing gnupg curl groff less postgresql-13 \
    && curl https://cli-assets.heroku.com/install-ubuntu.sh | sh \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install

FROM ${HOST_ENVIRONMENT} as final

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt


COPY . /app
RUN python manage.py collectstatic --noinput --settings=flexibi_dst.settings.heroku