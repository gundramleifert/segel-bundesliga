#!/usr/bin/env python3
"""
Zitadel Test User Setup Script

Creates dedicated test users for E2E testing with pre-verified emails
and simplified login configuration.

Usage:
    python setup_test_users.py
"""

import json
import sys
from pathlib import Path
import urllib.request
import urllib.error


class ZitadelTestSetup:
    def __init__(self, base_url: str = "http://localhost:8081"):
        self.base_url = base_url.rstrip('/')
        self.pat = self._load_pat()
        self.project_id = None

    def _load_pat(self) -> str:
        """Load PAT from file."""
        pat_file = Path(__file__).parent / "zitadel-data" / "admin.pat"
        if pat_file.exists():
            return pat_file.read_text().strip()
        raise FileNotFoundError(f"PAT file not found: {pat_file}")

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make HTTP request to Zitadel API."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.pat}",
            "Content-Type": "application/json",
        }
        body = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            return {"error": True, "code": e.code, "message": error_body}
        except Exception as e:
            return {"error": True, "message": str(e)}

    def get_project_id(self) -> str:
        """Get the segel-bundesliga project ID."""
        result = self._request("POST", "/management/v1/projects/_search", {
            "queries": [{"nameQuery": {"name": "segel-bundesliga", "method": "TEXT_QUERY_METHOD_EQUALS"}}]
        })
        if result.get("result"):
            self.project_id = result["result"][0]["id"]
            return self.project_id
        raise ValueError("Project 'segel-bundesliga' not found. Run setup_zitadel.py first.")

    def simplify_login_policy(self):
        """Simplify login policy - no MFA, no email verification prompts."""
        print("\n[1/4] Simplifying login policy...")

        # Update login policy
        result = self._request("PUT", "/admin/v1/policies/login", {
            "allowUsernamePassword": True,
            "allowRegister": False,
            "allowExternalIdp": False,
            "forceMfa": False,
            "passwordlessType": "PASSWORDLESS_TYPE_NOT_ALLOWED",
            "hidePasswordReset": False,
            "ignoreUnknownUsernames": False,
            "defaultRedirectUri": "",
            "allowDomainDiscovery": False,
            "disableLoginWithEmail": False,
            "disableLoginWithPhone": True,
            "forceMfaLocalOnly": False,
            "mfaInitSkipLifetime": "2592000s"  # 30 days
        })

        if result.get("error"):
            print(f"  Warning: {result.get('message', 'Unknown error')}")
        else:
            print("  Login policy updated")

        # Remove all MFA factors
        for factor in ["SECOND_FACTOR_TYPE_OTP", "SECOND_FACTOR_TYPE_U2F"]:
            self._request("DELETE", f"/admin/v1/policies/login/second_factors/{factor}")

        for factor in ["MULTI_FACTOR_TYPE_U2F_WITH_VERIFICATION"]:
            self._request("DELETE", f"/admin/v1/policies/login/multi_factors/{factor}")

        print("  MFA factors removed")

    def create_test_user(self, username: str, password: str, first_name: str, last_name: str) -> str:
        """Create a test user with verified email."""
        print(f"\n[2/4] Creating test user '{username}'...")

        # Check if user already exists
        result = self._request("POST", "/management/v1/users/_search", {
            "queries": [{"userNameQuery": {"userName": username, "method": "TEXT_QUERY_METHOD_EQUALS"}}]
        })

        if result.get("result"):
            user_id = result["result"][0]["id"]
            print(f"  User already exists: {user_id}")
            # Update password for existing user
            self.set_user_password(user_id, password)
            return user_id

        # Create user with import (allows setting verified email and password directly)
        result = self._request("POST", "/management/v1/users/human/_import", {
            "userName": username,
            "profile": {
                "firstName": first_name,
                "lastName": last_name,
                "displayName": f"{first_name} {last_name}"
            },
            "email": {
                "email": f"{username}@localhost",
                "isEmailVerified": True
            },
            "password": password,
            "passwordChangeRequired": False
        })

        if result.get("error"):
            # Try alternative method if import fails
            print(f"  Import failed, trying alternative method...")
            result = self._request("POST", "/management/v1/users/human", {
                "userName": username,
                "profile": {
                    "firstName": first_name,
                    "lastName": last_name,
                    "displayName": f"{first_name} {last_name}"
                },
                "email": {
                    "email": f"{username}@localhost",
                    "isEmailVerified": True
                },
                "password": {
                    "password": password,
                    "changeRequired": False
                }
            })

        if result.get("userId"):
            user_id = result["userId"]
            print(f"  Created user: {user_id}")
            return user_id
        elif result.get("error"):
            print(f"  Error: {result.get('message', 'Unknown error')}")
            return None

        return None

    def grant_role_to_user(self, user_id: str, role: str):
        """Grant a role to a user."""
        print(f"\n[3/4] Granting {role} role to user...")

        if not self.project_id:
            self.get_project_id()

        result = self._request("POST", f"/management/v1/users/{user_id}/grants", {
            "projectId": self.project_id,
            "roleKeys": [role]
        })

        if result.get("error"):
            if "already exists" in str(result.get("message", "")).lower():
                print(f"  Role grant already exists")
            else:
                print(f"  Warning: {result.get('message', 'Unknown error')}")
        else:
            print(f"  Granted {role} role")

    def verify_user_email(self, user_id: str):
        """Verify a user's email address."""
        result = self._request("POST", f"/management/v1/users/{user_id}/email/_verify", {})
        if not result.get("error"):
            print("  Email verified")

    def set_user_password(self, user_id: str, password: str):
        """Set a user's password."""
        result = self._request("POST", f"/management/v1/users/{user_id}/password", {
            "password": password,
            "noChangeRequired": True
        })
        if result.get("error"):
            print(f"  Warning: Could not set password: {result.get('message', 'Unknown error')}")
        else:
            print(f"  Password updated")

    def run(self):
        """Run the complete test setup."""
        print("=" * 50)
        print("Zitadel Test User Setup")
        print("=" * 50)

        # Get project ID
        try:
            self.get_project_id()
            print(f"Project ID: {self.project_id}")
        except ValueError as e:
            print(f"Error: {e}")
            return False

        # Simplify login policy
        self.simplify_login_policy()

        # Create test user
        test_user_id = self.create_test_user(
            username="testuser",
            password="TestPass123#",
            first_name="Test",
            last_name="User"
        )

        if test_user_id:
            # Grant ADMIN role
            self.grant_role_to_user(test_user_id, "ADMIN")

        # Print summary
        print("\n" + "=" * 50)
        print("Setup Complete!")
        print("=" * 50)
        print(f"""
Test User Credentials:
  Username: testuser
  Password: TestPass123#

Alternative (admin):
  Username: admin@zitadel.localhost
  Password: Admin123!

Login Policy:
  - No MFA required
  - No email verification prompts
  - Simple username/password login
""")
        return True


def main():
    setup = ZitadelTestSetup()
    success = setup.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
