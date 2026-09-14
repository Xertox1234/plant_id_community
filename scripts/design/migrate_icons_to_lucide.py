#!/usr/bin/env python3
"""Migrate the Flutter app's Material icons to Lucide.

The web uses `lucide-react`. This maps every Material icon the app referenced to
its Lucide counterpart so both platforms draw the same glyphs at the same
stroke weight.

Lucide is an all-outlined set with no filled variants — which is the point:
"outlined" stops being a per-call-site choice. Where Material offered a
filled/outlined pair for selected state (`home` vs `home_outlined`), BOTH map to
the same Lucide glyph and selection is carried by colour and the indicator pill,
exactly as the web does it.

Every target is validated against the installed package before a single file is
written, so a typo fails loudly instead of producing a missing-glyph box.

Usage:  python3 scripts/design/migrate_icons_to_lucide.py [--check]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Tests assert on which glyph is rendered, so they migrate with the source.
ROOTS = [
    REPO / "plant_community_mobile" / "lib",
    REPO / "plant_community_mobile" / "test",
]
PKG = Path.home() / (
    ".pub-cache/hosted/pub.dev/lucide_icons_flutter-3.1.19/lib/lucide_icons.dart"
)

# Material icon name -> Lucide icon name.
MAPPING = {
    # navigation & chrome
    "home": "house", "home_outlined": "house",
    "search": "search", "settings": "settings",
    "chevron_right": "chevronRight", "arrow_back": "arrowLeft",
    "arrow_forward": "arrowRight", "close": "x", "check": "check",
    "more_vert": "ellipsisVertical", "refresh": "refreshCw", "sync": "refreshCw",
    "logout": "logOut", "link": "link", "history": "history",
    "circle": "circle", "upload": "upload", "send": "send", "edit": "pencil",
    # plants & care
    "eco": "leaf", "eco_outlined": "leaf", "grass": "sprout",
    "water_drop": "droplet", "wb_sunny": "sun", "thermostat": "thermometer",
    "air": "wind", "local_fire_department_outlined": "flame",
    "calendar_today_outlined": "calendar", "hourglass_top": "hourglass",
    "stethoscope": "stethoscope", "document_scanner_outlined": "scanLine",
    # capture & media
    "camera_alt": "camera", "add_a_photo_outlined": "camera",
    "add_photo_alternate_outlined": "imagePlus",
    "broken_image_outlined": "imageOff", "image_not_supported": "imageOff",
    "collections_bookmark": "library", "play_circle_outline": "circlePlay",
    "videocam_off_outlined": "videoOff", "volume_off": "volumeX",
    # people & social
    "person": "user", "person_outline": "user",
    "account_circle_outlined": "circleUser",
    "person_add_alt_1": "userPlus", "group_add": "userPlus",
    "group_add_outlined": "userPlus",
    "group": "users", "group_outlined": "users", "people": "users",
    "forum": "messagesSquare", "forum_outlined": "messagesSquare",
    "chat_bubble_outline": "messageCircle", "reply": "reply",
    "alternate_email": "atSign", "block": "ban",
    "add_reaction_outlined": "smilePlus",
    # A state pair: Material used filled-vs-outline for saved/unsaved. Lucide
    # has no filled bookmark, so saved becomes a DIFFERENT glyph — exactly what
    # the web does (`BookmarkCheck` / `Bookmark` in ThreadDetailPage.tsx).
    "bookmark": "bookmarkCheck", "bookmark_border": "bookmark",
    "push_pin": "pin", "push_pin_outlined": "pin",
    "emoji_events_outlined": "trophy", "workspace_premium_outlined": "award",
    "poll_outlined": "chartColumn", "book": "bookOpen",
    # status & feedback
    "error": "circleAlert", "error_outline": "circleAlert",
    "warning_amber_outlined": "triangleAlert",
    "check_circle": "circleCheck", "check_circle_outline": "circleCheck",
    "info_outline": "info", "help_outline": "circleHelp",
    "cloud_off_outlined": "cloudOff",
    "notifications_none": "bell", "notifications_outlined": "bell",
    "notifications_active": "bellRing",
    # forms & auth
    "mail_outline": "mail", "email_outlined": "mail", "lock_outline": "lock",
    "visibility_outlined": "eye", "remove_red_eye_outlined": "eye",
    "visibility_off_outlined": "eyeOff",
    "add": "plus", "location_on_outlined": "mapPin",
    # editor toolbar
    "format_bold": "bold", "format_italic": "italic",
    "format_list_bulleted": "list", "format_quote_outlined": "quote",
    "code": "code",
    # theme controls
    "light_mode": "sun", "dark_mode": "moon", "brightness_auto": "monitor",
    "palette": "palette", "auto_awesome": "sparkles",
    "auto_awesome_outlined": "sparkles",
}

LUCIDE_IMPORT = "import 'package:lucide_icons_flutter/lucide_icons.dart';\n"


def available_icons() -> set[str]:
    if not PKG.exists():
        sys.exit(f"lucide package not found at {PKG}; run `flutter pub get` first")
    return set(re.findall(r"static const IconData (\w+)", PKG.read_text()))


def main() -> int:
    check_only = "--check" in sys.argv
    icons = available_icons()

    # Validate the whole mapping BEFORE touching any file.
    missing = sorted({v for v in MAPPING.values() if v not in icons})
    if missing:
        sys.exit(f"mapping targets absent from lucide_icons_flutter: {missing}")
    print(f"✓ all {len(set(MAPPING.values()))} Lucide targets exist")

    used = set()
    for root in ROOTS:
        for f in root.rglob("*.dart"):
            used |= set(re.findall(r"\bIcons\.(\w+)", f.read_text()))
    unmapped = sorted(used - MAPPING.keys())
    if unmapped:
        sys.exit(f"Material icons with no mapping: {unmapped}")
    print(f"✓ all {len(used)} Material icons in lib/ + test/ are mapped")

    if check_only:
        return 0

    pattern = re.compile(r"\bIcons\.(" + "|".join(sorted(MAPPING, key=len, reverse=True)) + r")\b")
    touched = 0
    replaced = 0
    for f in sorted(x for root in ROOTS for x in root.rglob("*.dart")):
        src = f.read_text()
        if "Icons." not in src:
            continue
        new, n = pattern.subn(lambda m: f"LucideIcons.{MAPPING[m.group(1)]}", src)
        if not n:
            continue
        if LUCIDE_IMPORT not in new:
            # Place the package import with the other package imports so the
            # formatter keeps it; it is used immediately, in this same write.
            lines = new.split("\n")
            last = max(
                (i for i, l in enumerate(lines) if l.startswith("import 'package:")),
                default=-1,
            )
            lines.insert(last + 1, LUCIDE_IMPORT.rstrip("\n"))
            new = "\n".join(lines)
        f.write_text(new)
        touched += 1
        replaced += n
        print(f"  {n:3}  {f.relative_to(REPO)}")

    print(f"--- {replaced} icon references rewritten across {touched} files ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
