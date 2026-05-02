#!/usr/bin/env python3
"""Migration: move existing workspace state into per-persona subdirectory.

Before this change, all data lived in workspace/companion/ directly.
After migration, per-persona state moves to workspace/companion/{persona_name}/,
while shared items (avatars, token_stats) stay at the root.

Usage:
    cd ai-companion-ng
    python scripts/migrate_persona_isolation.py

This script is idempotent — safe to run multiple times.
"""

import shutil
from pathlib import Path

BASE = Path(__file__).parent.parent / "workspace" / "companion"
PERSONA_DIR = BASE / "default"

# Per-persona items to move into workspace/companion/default/
PER_PERSONA_ITEMS = [
    "memory",
    "conversations",
    "states",
    "preference.json",
    "trending_cache.json",
    "liveness.json",
    "anniversaries.json",
    "habits_state.json",
    "relationship_state.json",  # legacy root-level file (if exists)
]

# Items to keep at root (shared across personas)
SHARED_ITEMS = {"avatars", "token_stats.json", "companion.log"}


def migrate():
    if not BASE.exists():
        print(f"[skip] Workspace not found: {BASE}")
        return

    PERSONA_DIR.mkdir(parents=True, exist_ok=True)

    moved = 0
    skipped = 0

    for item_name in PER_PERSONA_ITEMS:
        src = BASE / item_name
        if not src.exists():
            skipped += 1
            print(f"  skip (not found): {item_name}")
            continue

        dst = PERSONA_DIR / item_name

        if dst.exists():
            # Destination already exists — merge directories, skip files
            if src.is_dir():
                for item in src.iterdir():
                    target = dst / item.name
                    if not target.exists():
                        if item.is_dir():
                            shutil.copytree(item, target)
                        else:
                            shutil.copy2(item, target)
                        moved += 1
                        print(f"  merge: {item} -> {target}")
                    else:
                        skipped += 1
                        print(f"  skip (exists): {item}")
                # Remove source directory after merge
                shutil.rmtree(src)
            else:
                skipped += 1
                print(f"  skip (exists): {item_name}")
        else:
            if src.is_dir():
                shutil.move(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))
            moved += 1
            print(f"  move: {src} -> {dst}")

    print(f"\nMigration complete: {moved} moved, {skipped} skipped")
    print(f"  Per-persona state -> {PERSONA_DIR}/")
    print(f"  Shared items stay   -> {BASE}/  ({', '.join(SHARED_ITEMS)})")


if __name__ == "__main__":
    print("=== Persona Isolation Migration ===")
    print(f"Source:      {BASE}/")
    print(f"Destination: {PERSONA_DIR}/")
    print()
    migrate()
