"""
Security testing utilities and configurations for the Plant Community application.

This module provides tools and configurations for automated security testing,
including static analysis, dependency scanning, and security test cases.
"""

import subprocess
import sys
import os
from typing import List, Dict, Any
import json


class SecurityTestSuite:
    """
    Automated security testing suite for the application.
    """
    
    def __init__(self):
        self.results = {
            'static_analysis': {},
            'dependency_scan': {},
            'django_security': {},
            'overall_score': 0
        }
    
    def run_bandit_scan(self) -> Dict[str, Any]:
        """
        Run Bandit static security analysis.
        
        Returns:
            Dictionary containing Bandit scan results
        """
        print("Running Bandit static security analysis...")
        
        try:
            # Run bandit on the apps directory
            result = subprocess.run([
                'bandit', '-r', 'apps/', '-f', 'json', '-o', 'bandit_report.json'
            ], capture_output=True, text=True, check=False)
            
            if os.path.exists('bandit_report.json'):
                with open('bandit_report.json', 'r') as f:
                    bandit_data = json.load(f)
                
                # Parse results
                results = {
                    'high_severity': len([r for r in bandit_data.get('results', []) if r.get('issue_severity') == 'HIGH']),
                    'medium_severity': len([r for r in bandit_data.get('results', []) if r.get('issue_severity') == 'MEDIUM']),
                    'low_severity': len([r for r in bandit_data.get('results', []) if r.get('issue_severity') == 'LOW']),
                    'total_issues': len(bandit_data.get('results', [])),
                    'status': 'completed'
                }
                
                # Clean up
                os.remove('bandit_report.json')
                
                return results
            else:
                return {'status': 'failed', 'error': 'No report generated'}
                
        except FileNotFoundError:
            return {
                'status': 'skipped', 
                'error': 'Bandit not installed. Install with: pip install bandit'
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def run_safety_scan(self) -> Dict[str, Any]:
        """
        Run Safety dependency vulnerability scan.
        
        Returns:
            Dictionary containing Safety scan results
        """
        print("Running Safety dependency vulnerability scan...")
        
        try:
            # Run safety check
            result = subprocess.run([
                'safety', 'check', '--json'
            ], capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                return {
                    'status': 'clean',
                    'vulnerabilities': 0,
                    'message': 'No known vulnerabilities found'
                }
            else:
                try:
                    safety_data = json.loads(result.stdout)
                    return {
                        'status': 'vulnerabilities_found',
                        'vulnerabilities': len(safety_data),
                        'details': safety_data[:5],  # First 5 vulnerabilities
                        'message': f'Found {len(safety_data)} known vulnerabilities'
                    }
                except json.JSONDecodeError:
                    return {
                        'status': 'completed',
                        'message': result.stdout or result.stderr
                    }
                    
        except FileNotFoundError:
            return {
                'status': 'skipped',
                'error': 'Safety not installed. Install with: pip install safety'
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def run_django_security_check(self) -> Dict[str, Any]:
        """
        Run Django's built-in security check.
        
        Returns:
            Dictionary containing Django security check results
        """
        print("Running Django security check...")
        
        try:
            # Run Django's check command with security tags
            result = subprocess.run([
                'python', 'manage.py', 'check', '--deploy', '--fail-level', 'INFO'
            ], capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                return {
                    'status': 'passed',
                    'issues': 0,
                    'message': 'All Django security checks passed'
                }
            else:
                # Parse the output to count issues
                lines = result.stderr.split('\n')
                errors = [line for line in lines if 'ERROR' in line]
                warnings = [line for line in lines if 'WARNING' in line]
                
                return {
                    'status': 'issues_found',
                    'errors': len(errors),
                    'warnings': len(warnings),
                    'total_issues': len(errors) + len(warnings),
                    'details': result.stderr
                }
                
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def check_secret_files(self) -> Dict[str, Any]:
        """
        Check for presence of secret files that shouldn't be in version control.
        
        Returns:
            Dictionary containing secret file check results
        """
        print("Checking for exposed secret files...")
        
        # Files that should not be in version control
        secret_patterns = [
            '.env',
            'secret_key.txt',
            'private.key',
            '*.pem',
            'credentials.json',
            'config.ini'
        ]
        
        found_secrets = []
        
        # Check for .env files
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.startswith('.env') and file != '.env.example':
                    found_secrets.append(os.path.join(root, file))
                elif any(file.endswith(pattern.replace('*', '')) for pattern in secret_patterns if '*' in pattern):
                    found_secrets.append(os.path.join(root, file))
                elif file in secret_patterns:
                    found_secrets.append(os.path.join(root, file))
        
        return {
            'status': 'completed',
            'secrets_found': len(found_secrets),
            'files': found_secrets[:10],  # First 10 files
            'safe': len(found_secrets) == 0
        }
    
    def check_security_headers(self) -> Dict[str, Any]:
        """
        Check if security headers are properly configured.
        
        Returns:
            Dictionary containing security headers check results
        """
        print("Checking security headers configuration...")
        
        # Read settings file to check for security headers
        try:
            with open('plant_community_backend/settings.py', 'r') as f:
                settings_content = f.read()
            
            security_checks = {
                'SECURE_BROWSER_XSS_FILTER': 'SECURE_BROWSER_XSS_FILTER = True' in settings_content,
                'SECURE_CONTENT_TYPE_NOSNIFF': 'SECURE_CONTENT_TYPE_NOSNIFF = True' in settings_content,
                'X_FRAME_OPTIONS': 'X_FRAME_OPTIONS' in settings_content,
                'SECURE_HSTS_SECONDS': 'SECURE_HSTS_SECONDS' in settings_content,
                'CSP_DEFAULT_SRC': 'CSP_DEFAULT_SRC' in settings_content,
                'SESSION_COOKIE_SECURE': 'SESSION_COOKIE_SECURE' in settings_content,
                'CSRF_COOKIE_SECURE': 'CSRF_COOKIE_SECURE' in settings_content,
                'SESSION_COOKIE_HTTPONLY': 'SESSION_COOKIE_HTTPONLY' in settings_content,
            }
            
            configured = sum(security_checks.values())
            total = len(security_checks)
            
            return {
                'status': 'completed',
                'configured_headers': configured,
                'total_headers': total,
                'score': (configured / total) * 100,
                'details': security_checks
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def run_all_tests(self) -> Dict[str, Any]:
        """
        Run all security tests and generate a comprehensive report.
        
        Returns:
            Dictionary containing all test results and overall score
        """
        print("=" * 60)
        print("PLANT COMMUNITY WEB APP - SECURITY TEST SUITE")
        print("=" * 60)
        
        # Run all tests
        self.results['static_analysis'] = self.run_bandit_scan()
        self.results['dependency_scan'] = self.run_safety_scan()
        self.results['django_security'] = self.run_django_security_check()
        self.results['secret_files'] = self.check_secret_files()
        self.results['security_headers'] = self.check_security_headers()
        
        # Calculate overall score
        score = 0
        max_score = 100
        
        # Static analysis scoring (25 points)
        if self.results['static_analysis'].get('status') == 'completed':
            high = self.results['static_analysis'].get('high_severity', 0)
            medium = self.results['static_analysis'].get('medium_severity', 0)
            low = self.results['static_analysis'].get('low_severity', 0)
            
            if high == 0 and medium == 0 and low <= 2:
                score += 25
            elif high == 0 and medium <= 2:
                score += 20
            elif high == 0:
                score += 15
            else:
                score += max(0, 15 - (high * 5))
        
        # Dependency scanning (25 points)
        if self.results['dependency_scan'].get('status') == 'clean':
            score += 25
        elif self.results['dependency_scan'].get('vulnerabilities', 0) == 0:
            score += 25
        else:
            vuln_count = self.results['dependency_scan'].get('vulnerabilities', 0)
            score += max(0, 25 - (vuln_count * 5))
        
        # Django security (25 points)
        if self.results['django_security'].get('status') == 'passed':
            score += 25
        else:
            errors = self.results['django_security'].get('errors', 0)
            warnings = self.results['django_security'].get('warnings', 0)
            score += max(0, 25 - (errors * 5) - (warnings * 2))
        
        # Secret files (15 points)
        if self.results['secret_files'].get('safe', False):
            score += 15
        else:
            secrets = self.results['secret_files'].get('secrets_found', 0)
            score += max(0, 15 - (secrets * 5))
        
        # Security headers (10 points)
        if self.results['security_headers'].get('status') == 'completed':
            header_score = self.results['security_headers'].get('score', 0)
            score += (header_score / 100) * 10
        
        self.results['overall_score'] = min(score, max_score)
        
        return self.results
    
    def print_report(self):
        """Print a formatted security report."""
        results = self.results
        
        print("\n" + "=" * 60)
        print("SECURITY TEST RESULTS")
        print("=" * 60)
        
        # Overall score
        score = results['overall_score']
        if score >= 90:
            grade = "A (Excellent)"
        elif score >= 80:
            grade = "B (Good)"
        elif score >= 70:
            grade = "C (Fair)"
        elif score >= 60:
            grade = "D (Poor)"
        else:
            grade = "F (Critical Issues)"
        
        print(f"\nOVERALL SECURITY SCORE: {score:.1f}/100 - {grade}")
        
        # Static Analysis Results
        print(f"\n📊 STATIC ANALYSIS (Bandit):")
        static = results.get('static_analysis', {})
        if static.get('status') == 'completed':
            print(f"   High Severity Issues: {static.get('high_severity', 0)}")
            print(f"   Medium Severity Issues: {static.get('medium_severity', 0)}")
            print(f"   Low Severity Issues: {static.get('low_severity', 0)}")
            print(f"   Total Issues: {static.get('total_issues', 0)}")
        else:
            print(f"   Status: {static.get('status', 'unknown')}")
            if 'error' in static:
                print(f"   Error: {static['error']}")
        
        # Dependency Scan Results
        print(f"\n🔍 DEPENDENCY SCAN (Safety):")
        deps = results.get('dependency_scan', {})
        if deps.get('status') == 'clean':
            print("   ✅ No known vulnerabilities found")
        elif deps.get('status') == 'vulnerabilities_found':
            print(f"   ⚠️  Found {deps.get('vulnerabilities', 0)} vulnerabilities")
        else:
            print(f"   Status: {deps.get('status', 'unknown')}")
            if 'error' in deps:
                print(f"   Error: {deps['error']}")
        
        # Django Security Check
        print(f"\n🛡️  DJANGO SECURITY CHECK:")
        django = results.get('django_security', {})
        if django.get('status') == 'passed':
            print("   ✅ All security checks passed")
        else:
            print(f"   Errors: {django.get('errors', 0)}")
            print(f"   Warnings: {django.get('warnings', 0)}")
        
        # Secret Files Check
        print(f"\n🔒 SECRET FILES CHECK:")
        secrets = results.get('secret_files', {})
        if secrets.get('safe', False):
            print("   ✅ No exposed secret files found")
        else:
            print(f"   ⚠️  Found {secrets.get('secrets_found', 0)} potential secret files")
            if secrets.get('files'):
                for file in secrets['files'][:5]:
                    print(f"      - {file}")
        
        # Security Headers
        print(f"\n📋 SECURITY HEADERS:")
        headers = results.get('security_headers', {})
        if headers.get('status') == 'completed':
            score = headers.get('score', 0)
            print(f"   Configuration Score: {score:.1f}%")
            print(f"   Headers Configured: {headers.get('configured_headers', 0)}/{headers.get('total_headers', 0)}")
        
        print("\n" + "=" * 60)
        
        # Recommendations
        if score < 90:
            print("RECOMMENDATIONS:")
            if static.get('high_severity', 0) > 0:
                print("• 🚨 Fix high-severity static analysis issues immediately")
            if deps.get('vulnerabilities', 0) > 0:
                print("• 🔄 Update dependencies with known vulnerabilities")
            if django.get('errors', 0) > 0:
                print("• ⚙️  Fix Django security configuration errors")
            if not secrets.get('safe', False):
                print("• 🔐 Remove secret files from version control")
            if headers.get('score', 0) < 100:
                print("• 📡 Configure remaining security headers")
        else:
            print("✅ Excellent security posture! Keep up the good work.")
        
        print("=" * 60)


def main():
    """Run the security test suite."""
    suite = SecurityTestSuite()
    suite.run_all_tests()
    suite.print_report()


if __name__ == "__main__":
    main()