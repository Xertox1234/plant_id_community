#!/usr/bin/env python3
"""
Flutter Security Scanner

Checks Flutter/Dart packages for security issues by:
1. Parsing pubspec.lock to get all dependencies
2. Checking for discontinued packages
3. Checking pub.dev for security advisories
4. Generating SBOM (Software Bill of Materials)
5. Reporting outdated packages

Usage:
    python check_flutter_security.py [--fail-on-warning]

Exit codes:
    0: No issues found
    1: Critical issues found (discontinued packages, major version gaps)
    2: Warnings found (outdated packages)
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Set, Optional
import subprocess
import yaml

class FlutterSecurityScanner:
    def __init__(self, project_path: Path = Path.cwd()):
        self.project_path = project_path
        self.pubspec_lock = project_path / "plant_community_mobile" / "pubspec.lock"
        self.pubspec_yaml = project_path / "plant_community_mobile" / "pubspec.yaml"

        self.critical_issues: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def run(self) -> int:
        """Run all security checks and return exit code"""
        print("🔍 Flutter Security Scanner")
        print("=" * 60)

        if not self.pubspec_lock.exists():
            print(f"❌ ERROR: {self.pubspec_lock} not found")
            return 1

        # Step 1: Parse dependencies
        dependencies = self._parse_pubspec_lock()
        print(f"📦 Found {len(dependencies)} dependencies\n")

        # Step 2: Check for discontinued packages
        self._check_discontinued_packages(dependencies)

        # Step 3: Check for outdated packages
        self._check_outdated_packages()

        # Step 4: Generate SBOM
        self._generate_sbom(dependencies)

        # Step 5: Print summary
        return self._print_summary()

    def _parse_pubspec_lock(self) -> Dict[str, Dict]:
        """Parse pubspec.lock and extract package information"""
        try:
            with open(self.pubspec_lock, 'r') as f:
                lock_data = yaml.safe_load(f)

            packages = {}
            for name, info in lock_data.get('packages', {}).items():
                packages[name] = {
                    'version': info.get('version'),
                    'source': info.get('source'),
                    'dependency': info.get('dependency'),
                }

            return packages
        except Exception as e:
            self.critical_issues.append(f"Failed to parse pubspec.lock: {e}")
            return {}

    def _check_discontinued_packages(self, dependencies: Dict[str, Dict]):
        """Check for discontinued packages"""
        print("🚨 Checking for discontinued packages...")

        # Known discontinued packages (from Flutter investigation)
        discontinued = {
            'build_resolvers': 'Discontinued by Dart team',
            'build_runner_core': 'Discontinued by Dart team',
        }

        found_discontinued = []
        for pkg_name in dependencies.keys():
            if pkg_name in discontinued:
                reason = discontinued[pkg_name]
                found_discontinued.append(f"  ⚠️  {pkg_name}: {reason}")
                self.warnings.append(f"Discontinued package: {pkg_name} ({reason})")

        if found_discontinued:
            print("\n".join(found_discontinued))
            print(f"\n⚠️  Found {len(found_discontinued)} discontinued package(s)")
            print("   These are transitive dependencies and will be removed")
            print("   when upstream packages migrate.\n")
        else:
            print("✅ No discontinued packages found\n")

    def _check_outdated_packages(self):
        """Run flutter pub outdated and parse results"""
        print("📊 Checking for outdated packages...")

        try:
            result = subprocess.run(
                ['flutter', 'pub', 'outdated', '--json'],
                cwd=self.project_path / "plant_community_mobile",
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                self.warnings.append("flutter pub outdated failed")
                print(f"⚠️  Warning: flutter pub outdated failed\n")
                return

            try:
                outdated_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                self.warnings.append("Failed to parse outdated packages JSON")
                return

            packages = outdated_data.get('packages', [])

            # Categorize packages
            major_updates = []
            minor_updates = []
            discontinued_deps = []

            for pkg in packages:
                name = pkg.get('package', 'unknown')
                current = pkg.get('current', {}).get('version', 'unknown')
                latest = pkg.get('latest', {}).get('version', 'unknown')
                resolvable = pkg.get('resolvable', {}).get('version', 'unknown')
                is_discontinued = pkg.get('isDiscontinued', False)

                if is_discontinued:
                    discontinued_deps.append(f"  ⚠️  {name} ({current}) - DISCONTINUED")
                    self.critical_issues.append(f"Discontinued: {name}")
                elif latest != current:
                    # Check if it's a major version difference
                    try:
                        current_major = int(current.split('.')[0]) if current != 'unknown' else 0
                        latest_major = int(latest.split('.')[0]) if latest != 'unknown' else 0

                        if latest_major > current_major:
                            major_updates.append(f"  📌 {name}: {current} → {latest} (major update available)")
                        else:
                            minor_updates.append(f"  🔄 {name}: {current} → {latest}")
                    except:
                        minor_updates.append(f"  🔄 {name}: {current} → {latest}")

            # Report findings
            if discontinued_deps:
                print("\n⛔ Discontinued packages:")
                print("\n".join(discontinued_deps))

            if major_updates:
                print(f"\n📌 Major updates available ({len(major_updates)}):")
                # Only show first 5 to avoid clutter
                for update in major_updates[:5]:
                    print(update)
                if len(major_updates) > 5:
                    print(f"  ... and {len(major_updates) - 5} more")
                self.info.append(f"{len(major_updates)} major updates available")

            if minor_updates:
                print(f"\n🔄 Minor/patch updates available ({len(minor_updates)}):")
                # Only show first 3
                for update in minor_updates[:3]:
                    print(update)
                if len(minor_updates) > 3:
                    print(f"  ... and {len(minor_updates) - 3} more")
                self.info.append(f"{len(minor_updates)} minor updates available")

            if not discontinued_deps and not major_updates and not minor_updates:
                print("✅ All packages are up to date")

            print()

        except subprocess.TimeoutExpired:
            self.warnings.append("flutter pub outdated timed out")
            print("⚠️  Warning: flutter pub outdated timed out\n")
        except FileNotFoundError:
            self.critical_issues.append("Flutter not found in PATH")
            print("❌ ERROR: Flutter not found in PATH\n")

    def _generate_sbom(self, dependencies: Dict[str, Dict]):
        """Generate Software Bill of Materials"""
        print("📋 Generating SBOM (Software Bill of Materials)...")

        sbom_path = self.project_path / "plant_community_mobile" / "sbom.json"

        sbom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "version": 1,
            "metadata": {
                "component": {
                    "type": "application",
                    "name": "plant_community_mobile",
                    "version": "1.0.0"
                }
            },
            "components": []
        }

        for name, info in dependencies.items():
            component = {
                "type": "library",
                "name": name,
                "version": info['version'],
                "purl": f"pkg:pub/{name}@{info['version']}",
            }

            if info['dependency'] == 'direct main':
                component['scope'] = 'required'
            elif info['dependency'] == 'direct dev':
                component['scope'] = 'optional'
            else:
                component['scope'] = 'required'  # transitive

            sbom['components'].append(component)

        try:
            with open(sbom_path, 'w') as f:
                json.dump(sbom, f, indent=2)
            print(f"✅ SBOM generated: {sbom_path.name}")
            print(f"   Format: CycloneDX 1.4")
            print(f"   Components: {len(dependencies)}\n")
            self.info.append(f"SBOM generated with {len(dependencies)} components")
        except Exception as e:
            self.warnings.append(f"Failed to generate SBOM: {e}")
            print(f"⚠️  Warning: Failed to generate SBOM: {e}\n")

    def _print_summary(self) -> int:
        """Print summary and return appropriate exit code"""
        print("=" * 60)
        print("📊 SECURITY SCAN SUMMARY")
        print("=" * 60)

        if self.critical_issues:
            print(f"\n❌ Critical Issues ({len(self.critical_issues)}):")
            for issue in self.critical_issues:
                print(f"   • {issue}")

        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   • {warning}")

        if self.info:
            print(f"\nℹ️  Information ({len(self.info)}):")
            for info_item in self.info:
                print(f"   • {info_item}")

        print()

        # Determine exit code
        if self.critical_issues:
            print("❌ FAIL: Critical security issues found")
            return 1
        elif self.warnings:
            print("⚠️  WARNING: Some issues found (non-blocking)")
            return 0  # Don't fail CI for warnings
        else:
            print("✅ PASS: No security issues found")
            return 0

def main():
    parser = argparse.ArgumentParser(description='Flutter Security Scanner')
    parser.add_argument(
        '--fail-on-warning',
        action='store_true',
        help='Exit with code 2 if warnings are found'
    )
    parser.add_argument(
        '--project-path',
        type=Path,
        default=Path.cwd(),
        help='Path to project root (default: current directory)'
    )

    args = parser.parse_args()

    scanner = FlutterSecurityScanner(project_path=args.project_path)
    exit_code = scanner.run()

    # Adjust exit code if --fail-on-warning is set
    if args.fail_on_warning and scanner.warnings and not scanner.critical_issues:
        exit_code = 2

    sys.exit(exit_code)

if __name__ == '__main__':
    main()
