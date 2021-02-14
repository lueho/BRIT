cd ./db_dump
aws s3 cp s3://flexibi-dst/latest.dump latest.dump
SET PGPASSWORD=flexibi
SET POSTGRE_SQL_12_HOME=C:\Programme\PostgreSQL\12\bin
%POSTGRE_SQL_12_HOME%/pg_restore -Fc --no-acl --clean --no-owner -h localhost -d flexibi_dst -p 5433 -U flexibi_dst latest.dump
cd..