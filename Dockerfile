FROM python:3.8.3

RUN apt-get update
RUN apt-get install -y --no-install-recommends \
    cmake build-essential wget ca-certificates unzip pkg-config \
    zlib1g-dev libfreexl-dev libxml2-dev

WORKDIR /tmp

ENV CPUS 4

ENV WEBP_VERSION 1.0.0
RUN wget -q https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-${WEBP_VERSION}.tar.gz && \
    tar xzf libwebp-${WEBP_VERSION}.tar.gz && \
    cd libwebp-${WEBP_VERSION} && \
    CFLAGS="-O2 -Wl,-S" ./configure --enable-silent-rules && \
    echo "building WEBP ${WEBP_VERSION}..." \
    make --quiet -j${CPUS} && make --quiet install

ENV ZSTD_VERSION 1.3.4
RUN wget -q -O zstd-${ZSTD_VERSION}.tar.gz https://github.com/facebook/zstd/archive/v${ZSTD_VERSION}.tar.gz \
    && tar -zxf zstd-${ZSTD_VERSION}.tar.gz \
    && cd zstd-${ZSTD_VERSION} \
    && echo "building ZSTD ${ZSTD_VERSION}..." \
    && make --quiet -j${CPUS} ZSTD_LEGACY_SUPPORT=0 CFLAGS=-O1 \
    && make --quiet install ZSTD_LEGACY_SUPPORT=0 CFLAGS=-O1

ENV GEOS_VERSION 3.8.1
RUN wget -q https://download.osgeo.org/geos/geos-${GEOS_VERSION}.tar.bz2 \
    && tar -xjf geos-${GEOS_VERSION}.tar.bz2 \
    && cd geos-${GEOS_VERSION} \
    && ./configure --prefix=/usr/local \
    && echo "building geos ${GEOS_VERSION}..." \
    && make --quiet -j${CPUS} && make --quiet install

ENV SQLITE_VERSION 3270200
RUN wget -q https://www.sqlite.org/2019/sqlite-autoconf-${SQLITE_VERSION}.tar.gz \
    && tar -xzf sqlite-autoconf-${SQLITE_VERSION}.tar.gz && cd sqlite-autoconf-${SQLITE_VERSION} \
    && ./configure --prefix=/usr/local \
    && echo "building SQLITE ${SQLITE_VERSION}..." \
    && make --quiet -j${CPUS} && make --quiet install

ENV LIBTIFF_VERSION=4.1.0
RUN wget -q https://download.osgeo.org/libtiff/tiff-${LIBTIFF_VERSION}.tar.gz \
    && tar -xzf tiff-${LIBTIFF_VERSION}.tar.gz \
    && cd tiff-${LIBTIFF_VERSION} \
    && ./configure --prefix=/usr/local \
    && echo "building libtiff ${LIBTIFF_VERSION}..." \
    && make --quiet -j${CPUS} && make --quiet install

ENV CURL_VERSION 7.61.1
RUN wget -q https://curl.haxx.se/download/curl-${CURL_VERSION}.tar.gz \
    && tar -xzf curl-${CURL_VERSION}.tar.gz && cd curl-${CURL_VERSION} \
    && ./configure --prefix=/usr/local \
    && echo "building CURL ${CURL_VERSION}..." \
    && make --quiet -j${CPUS} && make --quiet install

ENV PROJ_VERSION 7.0.1
RUN wget -q https://download.osgeo.org/proj/proj-${PROJ_VERSION}.tar.gz \
    && tar -xzf proj-${PROJ_VERSION}.tar.gz \
    && cd proj-${PROJ_VERSION} \
    && ./configure --prefix=/usr/local \
    && echo "building proj ${PROJ_VERSION}..." \
    && make --quiet -j${CPUS} && make --quiet install

# Doesn't appear to be updated for proj6, not worth holding up the show
# ENV SPATIALITE_VERSION 4.3.0a
# RUN wget -q https://www.gaia-gis.it/gaia-sins/libspatialite-${SPATIALITE_VERSION}.tar.gz
# RUN tar -xzvf libspatialite-${SPATIALITE_VERSION}.tar.gz && cd libspatialite-${SPATIALITE_VERSION} \
#     && ./configure --prefix=/usr/local \
#     && echo "building SPATIALITE ${SPATIALITE_VERSION}..." \
#     && make --quiet -j${CPUS} && make --quiet install

ENV OPENJPEG_VERSION 2.3.1
RUN wget -q -O openjpeg-${OPENJPEG_VERSION}.tar.gz https://github.com/uclouvain/openjpeg/archive/v${OPENJPEG_VERSION}.tar.gz \
    && tar -zxf openjpeg-${OPENJPEG_VERSION}.tar.gz \
    && cd openjpeg-${OPENJPEG_VERSION} \
    && mkdir build && cd build \
    && cmake .. -DBUILD_THIRDPARTY:BOOL=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
    && echo "building openjpeg ${OPENJPEG_VERSION}..." \
    && make --quiet -j${CPUS} && make --quiet install

# TODO TileDB, NetCDF, PostgreSQL, SFCGAL, ODBC, FGDB, DODS, Spatiallite
ENV GDAL_SHORT_VERSION 3.1.0
ENV GDAL_VERSION 3.1.0
RUN wget -q https://download.osgeo.org/gdal/${GDAL_SHORT_VERSION}/gdal-${GDAL_VERSION}.tar.gz \
    && tar -xzf gdal-${GDAL_VERSION}.tar.gz && cd gdal-${GDAL_SHORT_VERSION} && \
    ./configure \
    --disable-debug \
    --disable-static \
    --prefix=/usr/local \
    --with-curl=/usr/local/bin/curl-config \
    --with-geos \
    --with-geotiff=internal \
    --with-hide-internal-symbols=yes \
    --with-libtiff=/usr/local \
    --with-openjpeg \
    --with-sqlite3 \
    --with-proj=/usr/local \
    --with-rename-internal-libgeotiff-symbols=yes \
    --with-rename-internal-libtiff-symbols=yes \
    --with-threads=yes \
    --with-webp=/usr/local \
    --with-zstd=/usr/local \
    && echo "building GDAL ${GDAL_VERSION}..." \
    && make --quiet -j${CPUS} && make --quiet install

RUN ldconfig

WORKDIR /app

# By copying over requirements first, we make sure that Docker will cache
# our installed requirements rather than reinstall them on every build
COPY ./requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Now copy in our code, and run it
COPY . /app
EXPOSE 8000

COPY ./entrypoint.sh /app/entrypoint.sh
#ENTRYPOINT /app/entrypoint.sh

CMD ["sh", "/app/entrypoint.sh"]