# How-Tos

This guide provides step-by-step instructions for common user tasks in BRIT.

---

> Developers: for testing instructions, see the Developer Guide → [Testing](../02_developer_guide/testing.md).

## Database Migrations
- Create new migrations:
  ```sh
  docker compose exec web python manage.py makemigrations
  ```
- Apply migrations:
  ```sh
  docker compose exec web python manage.py migrate
  ```

## Troubleshooting
- Check logs in `/logs/`
- View service output with:
  ```sh
  docker compose logs web
  ```

---

_Last updated: 2025-05-02_
