# References

This section provides reference material for BRIT configuration, management commands, and periodic tasks.

---

## Settings
- See `brit/settings/` for environment-specific configuration
- Sensitive values are managed via `.env` (never committed)

## Management Commands
- Custom commands in `brit/management/commands/`
- Run with:
  ```sh
  docker compose exec web python manage.py <command>
  ```

## Celery Beat Schedule
- Periodic tasks defined in Celery configuration
- See `celery.py` and related docs

---

_Last updated: 2025-05-02_
