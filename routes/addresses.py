"""Conservative interpretation of non-postal truck-stop address descriptions.

Original descriptions are retained. Census queries may omit exit directions
only when named cross roads establish a junction; no number or ZIP is invented.
"""

import re

EXIT = re.compile(r"\bEXITS?\s*[-:#]?\s*\d+[A-Z]?(?:\s*/\s*\d+[A-Z]?)?\b", re.I)
NUMBERED_STREET = re.compile(r"^(\d+[A-Z]?(?:-\d+)?)\s+\S", re.I)
ROAD = re.compile(
    r"\b(?:INTERSTATE|I)\s*[- ]?\s*\d+|\b(?:US(?:\s+HWY)?|U\.?S\.?\s+HIGHWAY)\s*[- ]?\s*\d+"
    r"|\b(?:SR|ST|STATE\s+(?:HWY|HIGHWAY|ROUTE|RTE)|ST\s+RT)\s*[- ]?\s*\d+"
    r"|\b(?:CR|(?:COUNTY|CO)\s+(?:ROAD|RD|HWY)|FM|FARM TO MARKET (?:ROAD|RD)|M)\s*[- ]?\s*[A-Z]?\d+"
    r"|\b[A-Z]{2}\s*[-]\s*\d+|\b(?:HWY|HIGHWAY)\s*[- ]?\s*\d+",
    re.I,
)
SUFFIXES = {
    "ROAD": "RD",
    "STREET": "ST",
    "AVENUE": "AVE",
    "BOULEVARD": "BLVD",
    "DRIVE": "DR",
    "LANE": "LN",
    "PARKWAY": "PKWY",
}


def conventional(address: str) -> bool:
    return bool(NUMBERED_STREET.match(address)) and not bool(
        re.search(r"\b(?:EXIT|MILES?|MILEPOST|MM)\b", address, re.I)
    )


def classify_address(address: str) -> str:
    """Exclusive priority: exit, numbered street, junction, highway, partial, other."""
    upper = " ".join(address.upper().split())
    if EXIT.search(upper) or re.search(r"\bEXIT\b", upper):
        return "exit_description"
    if conventional(upper):
        return "conventional_street"
    if re.search(r"[&/]|\bAND\b|\bAT\b", upper):
        return "intersection"
    if ROAD.search(upper) or re.search(r"TURNPIKE|NJTP|TOLL|\bMILE\s*(?:POST|MARKER)|\bMM\b", upper):
        return "highway_interstate"
    if not re.search(r"[A-Z]", upper) or len(upper) < 4 or re.match(r"^P\.?\s*O\.?\s*BOX\b", upper):
        return "malformed_partial"
    return "other"


def normalize_census_address(address: str) -> str:
    text = " ".join(address.upper().split()).strip(" ,;.")
    # Unambiguous common interstate typo in this dataset; it is not a house number.
    text = re.sub(r"^1-(\d+)\b(?=.*\bEXIT\b)", r"I-\1", text)
    text = re.sub(r"\b(?:INTERSTATE|I)\s*[- ]?\s*(\d+)\b", r"INTERSTATE \1", text)
    text = re.sub(r"\bU\.?S\.?\s*[- ]?\s*(\d+)\b", r"US HIGHWAY \1", text)
    text = re.sub(r"\b(?:SR|ST RT|STATE ROUTE)\s*[- ]?\s*(\d+)\b", r"STATE HIGHWAY \1", text)
    text = re.sub(r"\bCR\s*[- ]?\s*([A-Z]?\d+)\b", r"COUNTY ROAD \1", text)
    text = re.sub(r"\bFM\s*[- ]?\s*(\d+)\b", r"FARM TO MARKET ROAD \1", text)
    # Removing an exit number prevents Census mistaking it for a house number.
    # Only submit the named junction when at least two road identifiers exist.
    without_exit = EXIT.sub("", text)
    named_junction = bool(re.search(r"&.*\b(?:RD|ROAD|ST|STREET|AVE|AVENUE|DR|DRIVE|BLVD)\b", without_exit))
    if EXIT.search(text) and (len(ROAD.findall(without_exit)) >= 2 or named_junction):
        text = without_exit
    text = re.sub(r"\s*[,;]\s*", " ", text)
    text = re.sub(r"\s*([&/])\s*", r" \1 ", text)
    text = " ".join(text.split()).strip(" ,;")
    for word, abbreviation in SUFFIXES.items():
        # Keep highway classifications stable; standardize street suffixes only.
        if conventional(text):
            text = re.sub(rf"\b{word}\b", abbreviation, text)
    return text


def match_rejection(address: str, city: str, matched_address: str) -> str | None:
    parts = [part.strip() for part in matched_address.split(",")]
    if len(parts) < 3:
        return "invalid_matched_address"
    street = parts[0]
    source_number = NUMBERED_STREET.match(address) if conventional(address) else None
    matched_number = NUMBERED_STREET.match(street)
    if source_number:
        if not matched_number or source_number[1].upper() != matched_number[1].upper():
            return "changed_house_number"
    elif matched_number:
        return "invented_house_number"

    # Census sometimes ignores the supplied city and returns a same-state road
    # hundreds of miles away. Conservative exact city comparison avoids that.
    def city_key(value: str) -> str:
        value = re.sub(r"\bSAINT\b", "ST", value.upper())
        return re.sub(r"[^A-Z0-9]", "", value)

    if city_key(parts[-3]) != city_key(city):
        return "different_city"

    # Retain road identifiers; reject I-15 -> 15th Avenue reinterpretations.
    def road_identifiers(value: str) -> set[tuple[str, str]]:
        result = set()
        for road in ROAD.findall(value.upper()):
            number = re.search(r"[A-Z]?\d+$", road)[0]
            if re.match(r"INTERSTATE|I\b", road):
                kind = "interstate"
            elif re.match(r"U\.?S\.?\b", road):
                kind = "us"
            elif re.match(r"CR\b|COUNTY\b|CO\b", road):
                kind = "county"
            elif re.match(r"FM\b|FARM\b", road):
                kind = "farm"
            elif re.match(r"HWY\b|HIGHWAY\b", road):
                kind = "unspecified"
            else:
                kind = "state"
            result.add((kind, number))
        return result

    expected, actual = road_identifiers(address), road_identifiers(street)
    if not source_number and expected:
        for kind, number in actual:
            if (kind, number) not in expected and not (
                kind == "unspecified" and any(n == number for _, n in expected)
            ):
                return "changed_road_identifier"
        interstate = {road for road in expected if road[0] == "interstate"}
        if len(actual) < min(2, len(expected)) or not interstate <= actual:
            return "changed_road_identifier"
    return None
