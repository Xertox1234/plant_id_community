#!/usr/bin/env python3
"""Report Flutter routes that NO screen navigates to.

Why this exists: on 2026-09-12 the app shipped to TestFlight with 12 of 17
routes reachable from nothing -- roughly 16,800 lines of finished UI, including
the entire forum and the whole auth flow, with no way to open any of it. Nothing
in the repo revealed that. The routes were declared, registered and compiled;
the widget tests passed. Only the relationship between them was broken, and
nothing looked at relationships. See todos/384.

This checks REACHABILITY, not existence. A route can be declared, registered,
and covered by tests while being unreachable by a user -- which is exactly what
happened. Compare todos/383 item 11: `find.text` proves a widget is in the
TREE, not that anyone can get to it.

Exit codes, deliberately distinct -- "could not look" is never success:
  0  every route is reachable (or an allowed, documented orphan)
  1  one or more routes are unreachable
  2  could not analyse (files missing, nothing parsed)
"""
import re
import sys
from pathlib import Path

MOBILE = Path(__file__).resolve().parent.parent / "plant_community_mobile"
ROUTER = MOBILE / "lib/core/routing/app_router.dart"
LIB = MOBILE / "lib"

# Routes that are legitimately not the target of a context.go/push.
# Each entry needs a reason -- an unexplained entry here silently recreates the
# very bug this script exists to catch.
ALLOWED_ORPHANS = {
    "splash": "GoRouter initialLocation; entered by the router itself, not navigated to",
}


def die(msg: str) -> "None":
    print(f"INDETERMINATE: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    if not ROUTER.is_file():
        die(f"router not found at {ROUTER}")
    router = ROUTER.read_text()

    consts = dict(re.findall(r"static const (\w+)\s*=\s*'([^']+)'", router))
    if not consts:
        die("parsed zero route constants from AppRoutes -- the file shape changed")

    registered = set(re.findall(r"path:\s*AppRoutes\.(\w+)", router))
    if not registered:
        die("parsed zero registered GoRoutes -- the file shape changed")

    navs: "dict[str, set[str]]" = {}
    for f in sorted(LIB.rglob("*.dart")):
        if f == ROUTER:
            continue  # the router declares routes; it does not make them reachable
        for m in re.finditer(
            r"context\.(?:go|push|replace|pushReplacement|goNamed|pushNamed)\("
            r"\s*AppRoutes\.(\w+)", f.read_text()
        ):
            navs.setdefault(m.group(1), set()).add(f.relative_to(MOBILE).as_posix())

    print(f"{'route':<20} {'path':<24} {'registered':<11} reached from")
    print("-" * 96)
    orphans, unregistered = [], []
    for name, path in sorted(consts.items(), key=lambda kv: kv[1]):
        reg = name in registered
        srcs = sorted(navs.get(name, ()))
        if not reg:
            unregistered.append(name)
        if srcs:
            where = ", ".join(s.split("/")[-1] for s in srcs)
        elif name in ALLOWED_ORPHANS:
            where = f"(allowed: {ALLOWED_ORPHANS[name]})"
        else:
            where = "*** NOTHING ***"
            orphans.append(name)
        print(f"{name:<20} {path:<24} {'yes' if reg else 'NO':<11} {where[:48]}")

    print()
    if unregistered:
        print(f"NOT REGISTERED as a GoRoute ({len(unregistered)}): {', '.join(unregistered)}")
    if orphans:
        print(f"UNREACHABLE ({len(orphans)} of {len(consts)}): {', '.join(orphans)}")
        print("\nA user cannot open these. Either wire them into the navigation "
              "shell or add them to ALLOWED_ORPHANS with a reason.")
        return 1
    print(f"All {len(consts)} routes are reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
