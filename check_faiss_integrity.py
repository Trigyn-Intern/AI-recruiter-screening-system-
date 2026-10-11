#!/usr/bin/env python3
"""Check FAISS metadata integrity."""

import json
from pathlib import Path

metadata_path = Path("vector_store/resume_metadata.json")
if metadata_path.exists():
    data = json.loads(metadata_path.read_text())
    print("FAISS Metadata Integrity Check")
    print("=" * 60)
    print(f"Total metadata entries: {len(data)}")

    # Check row validity
    rows = [int(item.get("faiss_row", -1)) for item in data]
    print(f"Row range: {min(rows)} to {max(rows)}")
    print(f"Expected index size: {max(rows) + 1} (0-indexed)")

    # Check for duplicates
    if len(rows) == len(set(rows)):
        print("✓ No duplicate faiss_row values")
    else:
        print("✗ Found duplicate faiss_row values")

    # Check resume_id format
    valid_ids = sum(
        1
        for item in data
        if "resume_id" in item
        and isinstance(item["resume_id"], str)
        and len(item["resume_id"]) > 0
    )
    print(f"✓ Valid resume_id entries: {valid_ids}/{len(data)}")

    print("\nMetadata sample:")
    for i, item in enumerate(data[:3]):
        print(
            f'  {i+1}. {item["resume_name"]}: row={item["faiss_row"]}, '
            f'id_len={len(item["resume_id"])}'
        )
