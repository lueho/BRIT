cd ./db_dump
SET PGPASSWORD=flexibi
SET POSTGRE_SQL_12_HOME=C:\Programme\PostgreSQL\12\bin
%POSTGRE_SQL_12_HOME%/pg_dump -Fc --no-acl --no-owner -h localhost -p 5433 -U flexibi_dst > backup2.dump
aws s3 cp backup2.dump s3://flexibi-dst/backup2.dump
cd..