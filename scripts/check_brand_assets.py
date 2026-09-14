#!/usr/bin/env python3
"""Assert the shipped app icons and launch images really carry the brand mark.

WHY THIS EXISTS -- for every build up to iOS build 11, the app shipped Flutter's
default placeholder icon. `flutter build ipa` printed the warning on every single
run ("App icon is set to the default placeholder icon") and nothing failed, so it
scrolled past a hundred times. A warning nobody is forced to read is not a check.

WHAT IT ACTUALLY CHECKS, and why each one:

  1. Every icon exists and is a readable PNG at the exact size the asset
     catalogue claims. A truncated or mis-sized icon is an App Store rejection.
  2. No alpha channel. Apple rejects app icons containing one. Chromium always
     writes RGBA, so the renderer re-encodes; this proves the re-encode happened.
  3. The pixels are the BRAND's. A file can be the right size, opaque, and still
     be the placeholder -- so the corner pixel must be the pine tile and the
     image must carry the leaf's mint. Both colours are read from the canonical
     SVG rather than hardcoded, so changing the mark changes the expectation.
  4. Not a flat fill. A solid rectangle of tile colour would satisfy (1)-(3)'s
     corner test; requiring several distinct colours rules out a blank render.

STDLIB ONLY, DELIBERATELY. Pillow exists in backend/venv and nowhere else, and
CI invokes this repo's checks as a bare `python3 scripts/check_*.py` with no
venv active. A guard that only runs when a particular venv happens to be on PATH
is a guard that silently stops running -- the same reasoning as
plant_community_mobile/scripts/asc_build_numbers.py.

Usage:
    python3 scripts/check_brand_assets.py
    python3 scripts/check_brand_assets.py --json

Exit codes:
    0  every asset carries the mark
    1  at least one asset is missing, malformed, or not the mark
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MOBILE = REPO / "plant_community_mobile"
ICONSET = MOBILE / "ios/Runner/Assets.xcassets/AppIcon.appiconset"
LAUNCHSET = MOBILE / "ios/Runner/Assets.xcassets/LaunchImage.imageset"
RES = MOBILE / "android/app/src/main/res"
SVG = REPO / "web/public/favicon.svg"

ANDROID = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
LAUNCH = {"LaunchImage.png": 120, "LaunchImage@2x.png": 240, "LaunchImage@3x.png": 360}

# Flutter's placeholder is a blue-on-white Flutter logo; its corner is pure
# white. Named so a failure says what it found rather than just "wrong colour".
PLACEHOLDER_CORNER = (255, 255, 255)


class Fail(Exception):
    """A check failed for a reason worth printing verbatim."""


# ----------------------------------------------------------------- PNG ----


def decode_png(path: Path) -> tuple[int, int, int, bytes]:
    """Return (width, height, channels, pixels) for an 8-bit PNG.

    Deliberately narrow: handles what a renderer emits, and raises on anything
    else rather than guessing. A guess here would let a malformed icon pass.
    """
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise Fail(f"{path.name} is not a PNG")

    off, ihdr, idat = 8, None, []
    while off < len(raw):
        (length,) = struct.unpack(">I", raw[off : off + 4])
        ctype = raw[off + 4 : off + 8]
        data = raw[off + 8 : off + 8 + length]
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", data)
        elif ctype == b"IDAT":
            idat.append(data)
        elif ctype == b"IEND":
            break
        off += 12 + length

    if ihdr is None:
        raise Fail(f"{path.name} has no IHDR chunk")
    width, height, depth, colour, _, _, interlace = ihdr
    if depth != 8:
        raise Fail(f"{path.name} is {depth}-bit; expected 8-bit")
    if interlace:
        raise Fail(f"{path.name} is interlaced; expected non-interlaced")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(colour)
    if channels is None:
        raise Fail(f"{path.name} has unsupported PNG colour type {colour}")
    if not idat:
        raise Fail(f"{path.name} has no image data")

    stride = width * channels
    data = zlib.decompress(b"".join(idat))
    expected = (stride + 1) * height
    if len(data) != expected:
        raise Fail(
            f"{path.name} decompresses to {len(data)} bytes, expected {expected} "
            f"({width}x{height}, {channels} channels) -- truncated or malformed"
        )

    out = bytearray(stride * height)
    for y in range(height):
        f = data[y * (stride + 1)]
        src = data[y * (stride + 1) + 1 : (y + 1) * (stride + 1)]
        row = y * stride
        prior = row - stride
        for i in range(stride):
            a = out[row + i - channels] if i >= channels else 0
            b = out[prior + i] if y > 0 else 0
            c = out[prior + i - channels] if (y > 0 and i >= channels) else 0
            v = src[i]
            if f == 1:
                v += a
            elif f == 2:
                v += b
            elif f == 3:
                v += (a + b) // 2
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                v += a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            elif f != 0:
                raise Fail(f"{path.name} row {y} uses bad PNG filter {f}")
            out[row + i] = v & 0xFF
    return width, height, channels, bytes(out)


def pixel(px: bytes, channels: int, width: int, x: int, y: int) -> tuple[int, ...]:
    i = (y * width + x) * channels
    return tuple(px[i : i + channels])


# --------------------------------------------------------------- marks ----


def brand_colours() -> tuple[tuple[int, int, int], list[tuple[int, int, int]]]:
    """Read the tile's dark stop and the leaf's stops from the canonical SVG.

    Read, never hardcoded: an expectation that does not move with the mark is an
    expectation that goes stale silently the first time the mark is redrawn.
    """
    if not SVG.exists():
        raise Fail(f"canonical mark not found at {SVG.relative_to(REPO)}")
    svg = SVG.read_text()
    hexes = re.findall(r'stop-color="#([0-9A-Fa-f]{6})"', svg)
    if len(hexes) < 4:
        raise Fail(
            f"{SVG.relative_to(REPO)} declares {len(hexes)} gradient stops; "
            "expected at least 4 (tile x2, leaf x2). Cannot derive expectations."
        )
    rgb = lambda h: (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    # Document order: the tile gradient is declared before the leaf gradient.
    return rgb(hexes[0]), [rgb(h) for h in hexes[2:4]]


def near(a: tuple[int, ...], b: tuple[int, int, int], tol: int = 12) -> bool:
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def check_image(path: Path, size: int, *, opaque: bool, tile: tuple[int, int, int]):
    if not path.exists():
        raise Fail(f"missing: {path.relative_to(REPO)}")
    width, height, channels, px = decode_png(path)
    if (width, height) != (size, size):
        raise Fail(
            f"{path.relative_to(REPO)} is {width}x{height}, but the asset "
            f"catalogue requires {size}x{size}"
        )
    if opaque and channels in (2, 4):
        raise Fail(
            f"{path.relative_to(REPO)} has an alpha channel (PNG colour type "
            f"{'6' if channels == 4 else '4'}). Apple rejects app icons with one."
        )

    corner = pixel(px, channels, width, 0, 0)
    if near(corner, PLACEHOLDER_CORNER):
        raise Fail(
            f"{path.relative_to(REPO)} has a white corner -- this is still "
            f"Flutter's default placeholder icon, not the Houseplant MD mark."
        )
    if opaque and not near(corner, tile):
        raise Fail(
            f"{path.relative_to(REPO)} corner is rgb{corner}, expected the pine "
            f"tile rgb{tile}. The icon is not the brand mark."
        )

    distinct = {pixel(px, channels, width, x, y)[:3] for y in range(0, height, max(1, height // 16)) for x in range(0, width, max(1, width // 16))}
    if len(distinct) < 3:
        raise Fail(
            f"{path.relative_to(REPO)} samples only {len(distinct)} distinct "
            f"colour(s) -- a flat fill, not the mark."
        )
    return {"size": size, "channels": channels, "corner": list(corner[:3]), "distinct": len(distinct)}


def ios_targets() -> dict[str, int]:
    cj = json.loads((ICONSET / "Contents.json").read_text())
    out: dict[str, int] = {}
    for img in cj.get("images", []):
        if not img.get("filename"):
            continue
        px = round(float(img["size"].split("x")[0]) * float(img["scale"].rstrip("x")))
        out[img["filename"]] = px
    if not out:
        raise Fail("AppIcon.appiconset/Contents.json lists no icon filenames")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit results as JSON")
    args = ap.parse_args()

    failures: list[str] = []
    checked: dict[str, dict] = {}

    try:
        tile, leaf = brand_colours()
    except Fail as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    targets = []
    try:
        targets += [(ICONSET / f, px, True) for f, px in ios_targets().items()]
    except Fail as e:
        failures.append(str(e))
    targets += [(RES / d / "ic_launcher.png", px, True) for d, px in ANDROID.items()]
    targets += [(LAUNCHSET / f, px, False) for f, px in LAUNCH.items()]

    for path, size, opaque in targets:
        try:
            checked[str(path.relative_to(REPO))] = check_image(
                path, size, opaque=opaque, tile=tile
            )
        except Fail as e:
            failures.append(str(e))

    # The leaf's mint must appear SOMEWHERE in the marketing icon; the corner
    # test alone would pass on a plain gradient tile with no leaf drawn.
    big = ICONSET / "Icon-App-1024x1024@1x.png"
    if big.exists():
        try:
            w, h, ch, px = decode_png(big)
            step = max(1, w // 200)
            found = any(
                near(pixel(px, ch, w, x, y), leaf[0], tol=30)
                for y in range(0, h, step)
                for x in range(0, w, step)
            )
            if not found:
                failures.append(
                    f"{big.relative_to(REPO)} contains no pixel near the leaf's "
                    f"mint rgb{leaf[0]} -- the tile rendered but the leaf did not."
                )
        except Fail as e:
            failures.append(str(e))

    if args.json:
        print(json.dumps({"checked": checked, "failures": failures}, indent=2))
    else:
        print("=" * 60)
        print("BRAND ASSET CHECK")
        print("=" * 60)
        print(f"  canonical mark : {SVG.relative_to(REPO)}")
        print(f"  tile rgb{tile}   leaf rgb{leaf[0]}")
        print(f"  assets checked : {len(checked)}")
        for f in failures:
            print(f"  ✗ {f}")
        print()
        print(
            "❌ FAIL: " + f"{len(failures)} problem(s)"
            if failures
            else "✅ PASS: every icon and launch image carries the brand mark"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
