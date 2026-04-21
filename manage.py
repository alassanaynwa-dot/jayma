#!/usr/bin/env python
"""Utilitaire de ligne de commande Django pour Jayma."""
import os
import sys


def main():
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "config.settings.development"
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Impossible d'importer Django. Vérifie que le venv est activé "
            "et que Django est installé (pip install -r requirements-dev.txt)."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
