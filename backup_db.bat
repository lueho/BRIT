cd ./db_dump
heroku pg:backups:capture -a flexibi-dst HEROKU_POSTGRESQL_COPPER_URL
heroku pg:backups:download -a flexibi-dst
SET PGPASSWORD=flexibi
pg_restore --clean --no-acl --no-owner -h localhost -p 5433 -U flexibi_dst -d flexibi_dst latest.dump