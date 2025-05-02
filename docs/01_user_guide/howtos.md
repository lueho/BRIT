# How-Tos

This guide provides step-by-step instructions for common development and operational tasks in BRIT.

---

## Running Tests
- To run all tests (using a persistent DB and no prompts):
  ```sh
  docker compose exec web python manage.py test --keepdb --noinput > test_output.txt
  ```
- Review `test_output.txt` for results and troubleshooting.

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
