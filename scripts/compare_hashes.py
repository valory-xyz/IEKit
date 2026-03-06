#!/usr/bin/env python3
"""Compare package hashes between source-of-truth repos and target repo."""

import json
from pathlib import Path

# Source repos (dev + third_party packages from each)
SOURCE_REPOS = [
    Path("/Users/dhairya/Desktop/Work/Valory/Github/open-aea/packages/packages.json"),
    Path("/Users/dhairya/Desktop/Work/Valory/Github/open-autonomy/packages/packages.json"),
    Path("/Users/dhairya/Desktop/Work/Valory/Github/mech-interact/packages/packages.json"),
    Path("/Users/dhairya/Desktop/Work/Valory/Github/genai/packages/packages.json"),
]

# Target: this repo's packages.json
TARGET_PACKAGES_JSON = Path("packages/packages.json")


def main() -> None:
    """Compare hashes."""
    # Build combined source lookup (later repos overwrite earlier ones)
    source_all: dict = {}
    for source_path in SOURCE_REPOS:
        with open(source_path) as f:
            source = json.load(f)
        # Apply third_party first, then dev (dev takes priority within same repo)
        source_third = source.get("third_party", {})
        source_dev = source.get("dev", {})
        source_all.update(source_third)
        source_all.update(source_dev)

    with open(TARGET_PACKAGES_JSON) as f:
        target = json.load(f)

    target_third = target.get("third_party", {})

    mismatches = []
    missing = []
    for pkg, target_hash in target_third.items():
        if pkg in source_all:
            source_hash = source_all[pkg]
            if target_hash != source_hash:
                mismatches.append((pkg, target_hash, source_hash))
        else:
            missing.append(pkg)

    if not mismatches and not missing:
        print("All hashes match!")
        return

    if mismatches:
        print(f"Found {len(mismatches)} mismatched hashes:\n")
        for pkg, old, new in mismatches:
            print(f'  "{pkg}": "{new}",')
        print(f"\nReplace these in {TARGET_PACKAGES_JSON}")

    if missing:
        print(f"\n{len(missing)} packages not found in any source repo (left unchanged):")
        for pkg in missing:
            print(f"  {pkg}")


if __name__ == "__main__":
    main()
