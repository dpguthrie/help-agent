"""
Fix missing root spans by copying all data to a new project with proper root spans.

Copies all spans from the source project to a target project, creating synthetic
root spans for each trace so the hierarchy nests properly.

Usage:
    set -a; source .env; set +a
    .venv/bin/python scripts/fix_root_spans.py \
        --source-project-id <SOURCE_ID> \
        --target-project-id <TARGET_ID> \
        [--dry-run]
"""
from __future__ import annotations
import argparse
import json
import subprocess
import time
import requests
from collections import defaultdict


def bt_sql_json(project_id: str, select: str, where: str = "", limit: int = 500) -> list:
    """Run bt sql and return parsed results."""
    sql = f"SELECT {select} FROM project_logs('{project_id}')"
    if where:
        sql += f" WHERE {where}"
    sql += f" LIMIT {limit}"

    result = subprocess.run(
        ["bt", "sql", sql, "--json"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"  bt sql error: {result.stderr[:300]}")
        return []
    try:
        data = json.loads(result.stdout)
        return data.get("data", [])
    except json.JSONDecodeError:
        return []


def fetch_all_spans(api_url: str, project_id: str, headers: dict) -> list:
    """Fetch all spans from a project using the fetch API with pagination."""
    all_spans = []
    cursor = None
    page = 0

    while True:
        body = {"limit": 100}
        if cursor:
            body["cursor"] = cursor

        resp = requests.post(
            f"{api_url}/v1/project_logs/{project_id}/fetch",
            headers=headers,
            json=body,
            timeout=60,
        )
        if not resp.ok:
            print(f"  Fetch error (page {page}): {resp.status_code} {resp.text[:200]}")
            break

        data = resp.json()
        events = data.get("events", [])
        all_spans.extend(events)
        page += 1

        if page % 5 == 0:
            print(f"  Fetched {len(all_spans)} spans ({page} pages)...")

        cursor = data.get("cursor")
        if not cursor or not events:
            break

    return all_spans


def insert_spans(api_url: str, project_id: str, headers: dict, spans: list, batch_size: int = 50) -> tuple[int, int]:
    """Insert spans in batches. Returns (success_count, fail_count)."""
    success = 0
    failed = 0

    for i in range(0, len(spans), batch_size):
        batch = spans[i:i + batch_size]
        resp = requests.post(
            f"{api_url}/v1/project_logs/{project_id}/insert",
            headers=headers,
            json={"events": batch},
            timeout=60,
        )
        if resp.ok:
            success += len(batch)
        else:
            failed += len(batch)
            print(f"  Insert batch failed: {resp.status_code} {resp.text[:200]}")

        if (i + batch_size) % 200 == 0:
            print(f"  Inserted {success} spans...")

    return success, failed


def main():
    parser = argparse.ArgumentParser(description="Copy traces with fixed root spans")
    parser.add_argument("--source-project-id", required=True, help="Source Braintrust project ID")
    parser.add_argument("--target-project-id", required=True, help="Target Braintrust project ID")
    parser.add_argument("--api-key", required=True, help="Braintrust API key")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done")
    parser.add_argument("--api-url", default="https://api.braintrust.dev", help="Braintrust API URL")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.api_key}", "Content-Type": "application/json"}

    # Step 1: Fetch ALL spans from source project
    print(f"Fetching all spans from source project {args.source_project_id[:12]}...")
    all_spans = fetch_all_spans(args.api_url, args.source_project_id, headers)
    print(f"  Total spans: {len(all_spans)}")

    # Step 2: Group spans by root_span_id (trace)
    traces = defaultdict(list)
    for span in all_spans:
        root_id = span.get("root_span_id", "unknown")
        traces[root_id].append(span)

    print(f"  Traces: {len(traces)}")

    # Step 3: For each trace, find turns and create root spans
    root_spans_to_create = []
    for root_id, trace_spans in traces.items():
        # Find interaction.turn spans to get the session parent
        turns = [s for s in trace_spans if s.get("span_attributes", {}).get("name") == "interaction.turn"]
        if not turns:
            continue

        # Get the parent reference
        parents = set()
        for t in turns:
            for p in (t.get("span_parents") or []):
                parents.add(p)

        if not parents:
            continue

        session_parent = list(parents)[0]

        # Check if a root span already exists
        existing_root = any(
            s.get("span_id") == session_parent or s.get("is_root")
            for s in trace_spans
        )
        if existing_root:
            continue

        # Get time bounds from ALL spans in the trace
        starts = [s.get("metrics", {}).get("start", 0) for s in trace_spans if s.get("metrics", {}).get("start")]
        ends = [s.get("metrics", {}).get("end", 0) for s in trace_spans if s.get("metrics", {}).get("end")]

        root_span = {
            "id": session_parent,
            "span_id": session_parent,
            "root_span_id": root_id,
            "is_root": True,
            "span_parents": [],
            "span_attributes": {
                "name": "Session Help Agent",
                "type": "task",
            },
            "input": None,
            "output": None,
            "metadata": {
                "synthetic_root": True,
                "turn_count": len(turns),
                "total_spans": len(trace_spans),
            },
            "metrics": {
                "start": min(starts) if starts else time.time(),
                "end": max(ends) if ends else time.time(),
            },
        }
        root_spans_to_create.append(root_span)

    print(f"  Root spans to create: {len(root_spans_to_create)}")

    # Step 4: Prepare all spans for insertion (existing + new roots)
    # Clean up existing spans for re-insertion (remove internal fields)
    clean_spans = []
    for span in all_spans:
        clean = {
            "id": span.get("id"),
            "span_id": span.get("span_id"),
            "root_span_id": span.get("root_span_id"),
            "span_parents": span.get("span_parents"),
            "span_attributes": span.get("span_attributes"),
            "input": span.get("input"),
            "output": span.get("output"),
            "expected": span.get("expected"),
            "metadata": span.get("metadata"),
            "metrics": span.get("metrics"),
            "tags": span.get("tags"),
            "scores": span.get("scores"),
            "error": span.get("error"),
            "is_root": span.get("is_root", False),
        }
        # Remove None values
        clean = {k: v for k, v in clean.items() if v is not None}
        clean_spans.append(clean)

    all_to_insert = root_spans_to_create + clean_spans
    print(f"  Total spans to insert into target: {len(all_to_insert)} ({len(root_spans_to_create)} roots + {len(clean_spans)} existing)")

    if args.dry_run:
        print(f"\nDry run complete. Would insert {len(all_to_insert)} spans into {args.target_project_id[:12]}.")
        return

    # Step 5: Insert into target project
    print(f"\nInserting into target project {args.target_project_id[:12]}...")
    # Insert roots first so they exist when child spans reference them
    print("  Inserting root spans...")
    root_ok, root_fail = insert_spans(args.api_url, args.target_project_id, headers, root_spans_to_create)
    print(f"  Roots: {root_ok} ok, {root_fail} failed")

    print("  Inserting existing spans...")
    span_ok, span_fail = insert_spans(args.api_url, args.target_project_id, headers, clean_spans)
    print(f"  Spans: {span_ok} ok, {span_fail} failed")

    print(f"\nDone. Inserted {root_ok + span_ok} spans, {root_fail + span_fail} failed.")


if __name__ == "__main__":
    main()
