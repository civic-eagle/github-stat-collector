# Example for deleting all metrics within a project

```bash
poetry run python delete-metrics.py --project project1 $(poetry run python list-custom-metrics.py --project project1 2>/dev/null | xargs)
```
