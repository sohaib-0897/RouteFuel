import json
from pathlib import Path

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from routes.preprocessing import prepare


class Command(BaseCommand):
    help = "Prepare US fuel station coordinates once using Census batch and offline GeoNames centroids."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", type=Path, default=settings.BASE_DIR / "fuel-prices-for-be-assessment.csv"
        )
        parser.add_argument("--output", type=Path, default=settings.STATION_DATA_PATH)
        parser.add_argument("--refresh", action="store_true")
        parser.add_argument("--offline", action="store_true")

    def handle(self, *args, **options):
        try:
            stats = prepare(
                options["source"],
                options["output"],
                settings.BASE_DIR / ".cache/preprocessing",
                options["refresh"],
                options["offline"],
            )
        except (ValueError, OSError, httpx.HTTPError) as exc:
            raise CommandError(f"Preprocessing failed: {exc}") from exc
        self.stdout.write(json.dumps(stats, indent=2))
