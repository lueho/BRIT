FROM python:3.7

WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBUG 0

RUN apt-get update
RUN apt-get install -y --fix-missing binutils libproj-dev gdal-bin

# By copying over requirements first, we make sure that Docker will cache
# our installed requirements rather than reinstall them on every build
COPY ./requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Now copy in our code, and run it
COPY . /app
#EXPOSE 8000

COPY ./entrypoint.sh /app/entrypoint.sh
ENTRYPOINT /app/entrypoint.sh

CMD ["sh", "/app/entrypoint.sh"]