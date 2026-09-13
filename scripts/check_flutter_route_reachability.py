#!/usr/bin/env python3
"""Report Flutter routes that NO screen navigates to.

Why this exists: on 2026-09-12 the app shipped to TestFlight and the owner could
not find a way to log in. See todos/384.

This checks REACHABILITY, not existence. A route can be declared, registered,
and covered by tests while being unreachable by a user. Compare todos/383 item
11: `find.text` proves a widget is in the TREE, not that anyone can get to it.

HOW A ROUTE COUNTS AS REACHED -- four rules, each with a known limitation.
The first version of this script had only rule A, and that made it lie: it
reported 7 routes as orphans that a user could reach from the home screen on
the first tap (todo 384, corrections C1). A checker that cries wolf gets
ignored, so the rules below exist to make the verdict trustworthy, not to make
it green. Each is deliberately narrow.

  A. DIRECT      `context.go(AppRoutes.forum)` -- a literal constant passed to a
                 nav verb. Limitation: blind to every indirection below.

  B. NAMED       `context.pushNamed('forumBookmarks')` resolved against the
                 `name:` of the GoRoute whose `path:` is `AppRoutes.X`.
                 Limitation: a name built at runtime is invisible.

  C. FIELD       `route: AppRoutes.care` on a data class, dispatched later as
                 `context.push(feature.route)`. Counted ONLY when the same file
                 also contains a `context.<verb>(<ident>.route)` call, so a bare
                 mention of a constant never counts. Limitation: file-scoped --
                 a table in one file dispatched from another is missed.

  D. SHELL       a `StatefulShellBranch` root route, counted ONLY when the shell
                 widget file renders a matching destination. A branch declared
                 without a destination stays an orphan, which is the point.
                 Limitation: does not prove the destination is tappable -- that
                 is what test/routing/navigation_shell_test.dart is for.

WHAT THIS STILL CANNOT DO. There is no TRANSITIVE reachability: a route counts
as reached even if its only caller is itself unreachable. `login` read as
"reached from profile_screen.dart" for months while nothing could open
`profile`. Being reported reachable here is necessary, not sufficient.
Conversely, a nav call inside dead code would count. Satisfying this script is
not the same as being reachable, in either direction.

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
SHELL = MOBILE / "lib/core/routing/main_shell.dart"
LIB = MOBILE / "lib"

NAV_VERBS = r"go|push|replace|pushReplacement|goNamed|pushNamed"

# Routes that are legitimately not the target of a context.go/push.
# Each entry needs a reason -- an unexplained entry here silently recreates the
# very bug this script exists to catch.
ALLOWED_ORPHANS = {
    "splash": "GoRouter initialLocation; entered by the router itself, not navigated to",
    "garden": (
        "placeholder for the unbuilt garden-calendar feature; its 5 models "
        "(GardenBed/GardenPlant/CareTask/WeatherData -> apps/garden_calendar) "
        "are referenced by nothing in lib/ or test/. Deliberately not a shell "
        "destination -- there is no screen to show. Remove this entry when the "
        "feature is built (todo 384 follow-up)"
    ),
}

# Constants in AppRoutes that are NOT destinations. These are matched as path
# PREFIXES by the router's redirect, so they must exist and must not be
# registered as a GoRoute. Each needs a reason, same discipline as above.
# Anything unregistered and NOT listed here is still reported -- that line is
# the only thing that would catch the next AppRoutes.newThing nobody wired up.
PREFIX_CONSTANTS = {
    "forumGroups": (
        "guard prefix for /forum/groups/:id (todo 350); not a destination -- "
        "both children (/new, /:id) are registered, and no group-list screen "
        "exists (groups are folded into ForumConversationsScreen)"
    ),
}


def die(msg: str) -> "None":
    print(f"INDETERMINATE: {msg}", file=sys.stderr)
    raise SystemExit(2)


def route_blocks(router: str) -> "list[str]":
    """Slice the router source into one chunk per `GoRoute(`.

    Flat or nested, every route declaration begins with the same token, so
    slicing on it gives each route its own `path:`/`name:` pair.
    """
    starts = [m.start() for m in re.finditer(r"\bGoRoute\(", router)]
    return [router[a:b] for a, b in zip(starts, starts[1:] + [len(router)])]


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

    # Rule B: map a GoRoute's `name:` to the AppRoutes constant in its `path:`.
    name_to_const: "dict[str, str]" = {}
    for block in route_blocks(router):
        path = re.search(r"path:\s*AppRoutes\.(\w+)", block)
        name = re.search(r"name:\s*'(\w+)'", block)
        if path and name:
            name_to_const[name.group(1)] = path.group(1)
    if not name_to_const:
        die("parsed zero GoRoute name->path pairs -- the file shape changed")

    # Rule D: routes that are the root of a StatefulShellBranch, and the
    # destinations the shell widget actually renders.
    branch_roots = set()
    for m in re.finditer(r"StatefulShellBranch\((.*?)(?=StatefulShellBranch\(|\Z)",
                         router, re.S):
        first = re.search(r"path:\s*AppRoutes\.(\w+)", m.group(1))
        if first:
            branch_roots.add(first.group(1))
    shell_text = SHELL.read_text() if SHELL.is_file() else ""
    shell_destinations = set(re.findall(r"AppRoutes\.(\w+)", shell_text))

    navs: "dict[str, set[str]]" = {}

    def record(const: str, f: Path) -> None:
        navs.setdefault(const, set()).add(f.relative_to(MOBILE).as_posix())

    for f in sorted(LIB.rglob("*.dart")):
        if f == ROUTER:
            continue  # the router declares routes; it does not make them reachable
        src = f.read_text()

        # Rule A -- a literal constant handed to a nav verb.
        for m in re.finditer(rf"context\.(?:{NAV_VERBS})\(\s*AppRoutes\.(\w+)", src):
            record(m.group(1), f)

        # Rule B -- navigation by route name.
        for m in re.finditer(rf"context\.(?:goNamed|pushNamed|replaceNamed|"
                             rf"pushReplacementNamed)\(\s*'(\w+)'", src):
            const = name_to_const.get(m.group(1))
            if const:
                record(const, f)

        # Rule C -- a route stored on a data class and dispatched through it.
        # Requires BOTH halves in the same file, so a bare mention never counts.
        if re.search(rf"context\.(?:{NAV_VERBS})\(\s*\w+\.route\b", src):
            for m in re.finditer(r"route:\s*AppRoutes\.(\w+)", src):
                record(m.group(1), f)

        # Rule D -- a shell branch root, if this file renders its destination.
        if f == SHELL:
            for const in branch_roots & shell_destinations:
                record(const, f)

    print(f"{'route':<20} {'path':<24} {'registered':<11} reached from")
    print("-" * 96)
    orphans, unregistered, prefixes = [], [], []
    for name, path in sorted(consts.items(), key=lambda kv: kv[1]):
        if name in PREFIX_CONSTANTS:
            prefixes.append(name)
            continue
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
    for name in prefixes:
        print(f"PREFIX (not a destination): {name} = {consts[name]!r}")
        print(f"    {PREFIX_CONSTANTS[name]}")
    if unregistered:
        print(f"NOT REGISTERED as a GoRoute ({len(unregistered)}): {', '.join(unregistered)}")
        print("    Declared in AppRoutes but served by no GoRoute. Either register "
              "it,\n    delete it, or -- if it is a redirect guard prefix rather "
              "than a\n    destination -- add it to PREFIX_CONSTANTS with a reason.")
    if orphans:
        print(f"UNREACHABLE ({len(orphans)} of {len(consts)}): {', '.join(orphans)}")
        print("\nA user cannot open these. Either wire them into the navigation "
              "shell or add them to ALLOWED_ORPHANS with a reason.")
        return 1
    print(f"All {len(consts)} routes are reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
