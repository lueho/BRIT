# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.contrib.gis.db import models


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DashboardOrder(models.Model):
    product_category = models.CharField(max_length=20)
    payment_method = models.CharField(max_length=50)
    shipping_cost = models.CharField(max_length=50)
    unit_price = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'dashboard_order'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class TreesAuthor(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=40)
    email = models.CharField(max_length=254)

    class Meta:
        managed = False
        db_table = 'trees_author'


class TreesBook(models.Model):
    title = models.CharField(max_length=100)
    publication_date = models.DateField()
    publisher = models.ForeignKey('TreesPublisher', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'trees_book'


class TreesBookAuthors(models.Model):
    book = models.ForeignKey(TreesBook, models.DO_NOTHING)
    author = models.ForeignKey(TreesAuthor, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'trees_book_authors'
        unique_together = (('book', 'author'),)


class TreesHhRoadside(models.Model):
    id_0 = models.AutoField(primary_key=True)
    geom = models.PointField(blank=True, null=True)
    id = models.IntegerField(blank=True, null=True)
    baumid = models.IntegerField(blank=True, null=True)
    baumnummer = models.CharField(max_length=-1, blank=True, null=True)
    gattung = models.CharField(max_length=-1, blank=True, null=True)
    gattung_latein = models.CharField(max_length=-1, blank=True, null=True)
    gattung_deutsch = models.CharField(max_length=-1, blank=True, null=True)
    art = models.CharField(max_length=-1, blank=True, null=True)
    art_latein = models.CharField(max_length=-1, blank=True, null=True)
    art_deutsch = models.CharField(max_length=-1, blank=True, null=True)
    sorte_latein = models.CharField(max_length=-1, blank=True, null=True)
    sorte_deutsch = models.CharField(max_length=-1, blank=True, null=True)
    pflanzjahr = models.IntegerField(blank=True, null=True)
    pflanzjahr_portal = models.IntegerField(blank=True, null=True)
    kronendurchmesser = models.IntegerField(blank=True, null=True)
    kronendurchmesser_z = models.CharField(max_length=-1, blank=True, null=True)
    stammumfang = models.IntegerField(blank=True, null=True)
    stammumfang_z = models.CharField(max_length=-1, blank=True, null=True)
    strasse = models.CharField(max_length=-1, blank=True, null=True)
    hausnummer = models.CharField(max_length=-1, blank=True, null=True)
    ortsteil_nr = models.CharField(max_length=-1, blank=True, null=True)
    stadtteil = models.CharField(max_length=-1, blank=True, null=True)
    bezirk = models.CharField(max_length=-1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'trees_hh_roadside'


class TreesPublisher(models.Model):
    name = models.CharField(max_length=30)
    address = models.CharField(max_length=50)
    city = models.CharField(max_length=60)
    state_province = models.CharField(max_length=30)
    country = models.CharField(max_length=50)
    website = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = 'trees_publisher'
