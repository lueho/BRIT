FROM redis:7-alpine

RUN apk add --no-cache openssl

RUN wget https://raw.githubusercontent.com/redis/redis/cc0091f0f9fe321948c544911b3ea71837cf86e3/utils/gen-test-certs.sh
RUN chmod +x ./gen-test-certs.sh
RUN sh ./gen-test-certs.sh

COPY redis.conf /etc/redis/redis.conf

CMD ["redis-server", "/etc/redis/redis.conf"]
