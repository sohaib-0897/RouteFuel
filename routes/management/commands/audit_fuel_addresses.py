import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from routes.addresses import classify_address, normalize_census_address
from routes.preprocessing import parse_census, read_source


class Command(BaseCommand):
    help = "Classify US address patterns and cached Census outcomes without network calls."

    def add_arguments(self, parser):
        parser.add_argument("--census-response", type=Path)
        parser.add_argument("--output", type=Path)

    def handle(self, *args, **options):
        source = settings.BASE_DIR / "fuel-prices-for-be-assessment.csv"
        records, _ = read_source(source)
        with source.open(newline="", encoding="utf-8-sig") as stream:
            source_patterns = Counter(classify_address(row["Address"]) for row in csv.DictReader(stream))
        stats_path = settings.STATION_DATA_PATH.with_name("preprocessing_stats.json")
        current_cache_file = (
            json.loads(stats_path.read_text()).get("census_cache_file") if stats_path.exists() else None
        )
        response = options["census_response"] or settings.BASE_DIR / ".cache/preprocessing" / (
            current_cache_file or f"census-{hashlib.sha256(source.read_bytes()).hexdigest()}.csv"
        )
        try:
            with response.open(newline="", encoding="utf-8") as stream:
                statuses = {row[0]: row[2] for row in csv.reader(stream) if row}
        except OSError as exc:
            raise CommandError("Provide an existing cached Census response with --census-response.") from exc
        groups = defaultdict(Counter)
        rejections = Counter()
        accepted = parse_census(response.read_text(encoding="utf-8"), records, rejections)
        examples = defaultdict(list)
        changed = Counter()
        for record in records:
            kind = classify_address(record["address"])
            groups[kind][statuses.get(record["record_id"], "missing")] += 1
            normalized = normalize_census_address(record["address"])
            if normalized != record["address"]:
                changed[kind] += 1
            if len(examples[kind]) < 5:
                examples[kind].append({"original": record["address"], "census_query": normalized})
        result = {
            "source_category_counts": dict(sorted(source_patterns.items())),
            "us_unique_records": len(records),
            "accepted_census_coordinates": len(accepted),
            "rejected_census_matches": dict(sorted(rejections.items())),
            "exclusive_category_priority": [
                "exit_description",
                "conventional_street",
                "intersection",
                "highway_interstate",
                "malformed_partial",
                "other",
            ],
            "census_response_sha256": hashlib.sha256(response.read_bytes()).hexdigest(),
            "categories": {
                key: {
                    "records": sum(value.values()),
                    "outcomes": dict(value),
                    "normalized_queries": changed[key],
                    "examples": examples[key],
                }
                for key, value in sorted(groups.items())
            },
        }
        serialized = json.dumps(result, indent=2) + "\n"
        if options["output"]:
            options["output"].write_text(serialized, encoding="utf-8")
        self.stdout.write(serialized)
