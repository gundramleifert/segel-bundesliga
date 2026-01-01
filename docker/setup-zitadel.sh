#!/bin/bash
# Zitadel Setup Script for Segel-Bundesliga
#
# Prerequisites:
# 1. Log in to Zitadel Console: http://localhost:8081/ui/console
#    Username: admin
#    Password: Admin123!
# 2. Go to: admin (top right) -> Personal Access Tokens -> New
# 3. Copy the token and set it below or pass as argument

set -e

ZITADEL_URL="${ZITADEL_URL:-http://localhost:8081}"
PAT="${1:-$ZITADEL_PAT}"

if [ -z "$PAT" ]; then
    echo "Usage: $0 <personal-access-token>"
    echo "Or set ZITADEL_PAT environment variable"
    echo ""
    echo "To get a PAT:"
    echo "1. Open http://localhost:8081/ui/console"
    echo "2. Login with admin / Admin123!"
    echo "3. Click on your username (top right)"
    echo "4. Go to 'Personal Access Tokens'"
    echo "5. Click 'New' and copy the token"
    exit 1
fi

AUTH="Authorization: Bearer $PAT"
CT="Content-Type: application/json"

echo "=== Zitadel Setup for Segel-Bundesliga ==="
echo ""

# 1. Create Project
echo "Creating project 'segel-bundesliga'..."
PROJECT_RESPONSE=$(curl -s -X POST "$ZITADEL_URL/management/v1/projects" \
    -H "$AUTH" \
    -H "$CT" \
    -d '{
        "name": "segel-bundesliga",
        "projectRoleAssertion": true,
        "projectRoleCheck": true
    }')

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id // empty')
if [ -z "$PROJECT_ID" ]; then
    echo "Error creating project. Response: $PROJECT_RESPONSE"
    # Try to get existing project
    echo "Checking for existing project..."
    PROJECTS=$(curl -s -X POST "$ZITADEL_URL/management/v1/projects/_search" \
        -H "$AUTH" \
        -H "$CT" \
        -d '{"queries":[{"nameQuery":{"name":"segel-bundesliga","method":"TEXT_QUERY_METHOD_EQUALS"}}]}')
    PROJECT_ID=$(echo "$PROJECTS" | jq -r '.result[0].id // empty')
    if [ -z "$PROJECT_ID" ]; then
        echo "Could not find or create project"
        exit 1
    fi
    echo "Found existing project: $PROJECT_ID"
else
    echo "Created project: $PROJECT_ID"
fi

# 2. Create Roles
echo ""
echo "Creating roles..."

ROLES=(
    "ADMIN:Administrator with full access"
    "BLOG_WRITE:Can create and edit blog posts"
    "BLOG_PUBLISH:Can publish blog posts"
    "SPONSOR_MANAGE:Can manage sponsors"
    "PAIRING_EXECUTE:Can run pairing optimizations"
    "PAIRING_VIEW:Can view pairing results"
    "INTERNAL_ACCESS:Can access internal content"
)

for ROLE_DEF in "${ROLES[@]}"; do
    ROLE_KEY="${ROLE_DEF%%:*}"
    ROLE_DESC="${ROLE_DEF#*:}"

    ROLE_RESPONSE=$(curl -s -X POST "$ZITADEL_URL/management/v1/projects/$PROJECT_ID/roles" \
        -H "$AUTH" \
        -H "$CT" \
        -d "{
            \"roleKey\": \"$ROLE_KEY\",
            \"displayName\": \"$ROLE_KEY\",
            \"group\": \"segel-bundesliga\"
        }" 2>/dev/null)

    if echo "$ROLE_RESPONSE" | jq -e '.details' > /dev/null 2>&1; then
        echo "  Created role: $ROLE_KEY"
    else
        echo "  Role exists or error: $ROLE_KEY"
    fi
done

# 3. Create Backend API Application (for token validation)
echo ""
echo "Creating Backend API application..."
API_RESPONSE=$(curl -s -X POST "$ZITADEL_URL/management/v1/projects/$PROJECT_ID/apps/api" \
    -H "$AUTH" \
    -H "$CT" \
    -d '{
        "name": "segel-bundesliga-backend",
        "authMethodType": "API_AUTH_METHOD_TYPE_BASIC"
    }')

API_APP_ID=$(echo "$API_RESPONSE" | jq -r '.appId // empty')
API_CLIENT_ID=$(echo "$API_RESPONSE" | jq -r '.clientId // empty')
API_CLIENT_SECRET=$(echo "$API_RESPONSE" | jq -r '.clientSecret // empty')

if [ -n "$API_APP_ID" ]; then
    echo "  Created API app: $API_APP_ID"
    echo "  Client ID: $API_CLIENT_ID"
else
    echo "  API app might already exist"
fi

# 4. Create Frontend Web Application (for user login)
echo ""
echo "Creating Frontend Web application..."
WEB_RESPONSE=$(curl -s -X POST "$ZITADEL_URL/management/v1/projects/$PROJECT_ID/apps/oidc" \
    -H "$AUTH" \
    -H "$CT" \
    -d '{
        "name": "segel-bundesliga-frontend",
        "redirectUris": [
            "http://localhost:3000/callback",
            "http://localhost:3000/silent-refresh.html"
        ],
        "postLogoutRedirectUris": [
            "http://localhost:3000"
        ],
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"],
        "appType": "OIDC_APP_TYPE_USER_AGENT",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_NONE",
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
        "idTokenRoleAssertion": true,
        "idTokenUserinfoAssertion": true,
        "accessTokenRoleAssertion": true
    }')

WEB_APP_ID=$(echo "$WEB_RESPONSE" | jq -r '.appId // empty')
WEB_CLIENT_ID=$(echo "$WEB_RESPONSE" | jq -r '.clientId // empty')

if [ -n "$WEB_APP_ID" ]; then
    echo "  Created Web app: $WEB_APP_ID"
    echo "  Client ID: $WEB_CLIENT_ID"
else
    echo "  Web app might already exist, checking..."
    APPS=$(curl -s -X POST "$ZITADEL_URL/management/v1/projects/$PROJECT_ID/apps/_search" \
        -H "$AUTH" \
        -H "$CT" \
        -d '{}')
    WEB_CLIENT_ID=$(echo "$APPS" | jq -r '.result[] | select(.name=="segel-bundesliga-frontend") | .oidcConfig.clientId // empty')
fi

# 5. Grant admin user the ADMIN role
echo ""
echo "Granting ADMIN role to admin user..."

# Get admin user ID
USERS=$(curl -s -X POST "$ZITADEL_URL/management/v1/users/_search" \
    -H "$AUTH" \
    -H "$CT" \
    -d '{"queries":[{"userNameQuery":{"userName":"admin","method":"TEXT_QUERY_METHOD_EQUALS"}}]}')

ADMIN_USER_ID=$(echo "$USERS" | jq -r '.result[0].id // empty')

if [ -n "$ADMIN_USER_ID" ]; then
    GRANT_RESPONSE=$(curl -s -X POST "$ZITADEL_URL/management/v1/users/$ADMIN_USER_ID/grants" \
        -H "$AUTH" \
        -H "$CT" \
        -d "{
            \"projectId\": \"$PROJECT_ID\",
            \"roleKeys\": [\"ADMIN\"]
        }")
    echo "  Granted ADMIN role to admin user"
fi

# 6. Output configuration
echo ""
echo "=========================================="
echo "=== Configuration Complete ==="
echo "=========================================="
echo ""
echo "Add these to your .env file:"
echo ""
echo "# Zitadel Configuration"
echo "ZITADEL_ISSUER=$ZITADEL_URL"
echo "ZITADEL_PROJECT_ID=$PROJECT_ID"
echo "ZITADEL_WEB_CLIENT_ID=$WEB_CLIENT_ID"
if [ -n "$API_CLIENT_ID" ]; then
    echo "ZITADEL_API_CLIENT_ID=$API_CLIENT_ID"
    echo "ZITADEL_API_CLIENT_SECRET=$API_CLIENT_SECRET"
fi
echo ""
echo "Frontend .env:"
echo "VITE_ZITADEL_ISSUER=$ZITADEL_URL"
echo "VITE_ZITADEL_CLIENT_ID=$WEB_CLIENT_ID"
echo "VITE_ZITADEL_PROJECT_ID=$PROJECT_ID"
echo ""
echo "=========================================="
