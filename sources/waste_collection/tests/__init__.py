from django.db.backends.postgresql.features import DatabaseFeatures

DatabaseFeatures.can_defer_constraint_checks = False
