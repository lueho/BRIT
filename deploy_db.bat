cd db_dump
for /f "usebackq tokens=*" %i in (`aws s3 presign s3://flexibi-dst/latest.dump`) do heroku pg:backups:restore -a flexibi-dst --confirm flexibi-dst "%i" HEROKU_POSTGRESQL_COPPER_URL
cd..