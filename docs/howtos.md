# How-Tos

Step-by-step guides for common development and operational tasks in BRIT.

---

## Running Tests
- Run all tests (with persistent DB, no prompts):
  ```sh
  docker compose exec web python manage.py test --keepdb --noinput > test_output.txt
  ```
- Review `test_output.txt` for results and troubleshooting.

## Database Migrations
- Create new migration:
  ```sh
  docker compose exec web python manage.py makemigrations
  ```
- Apply migrations:
  ```sh
  docker compose exec web python manage.py migrate
  ```

## Troubleshooting
- Check logs in `/logs/`
- Use `docker compose logs web` for service output

---

_Last updated: 2025-05-02_
