#!/usr/bin/env bash
# ==============================================================================
# EchoCart Nexus - End-to-End Streamable HTTP & MCP Apps Verification Script
# Validates:
# 1. Health check & Readiness endpoint
# 2. Strict MCP-Protocol-Version: 2025-11-25 wire header enforcement
# 3. JSON-RPC handshake (initialize)
# 4. Tool discovery (tools/list) with _meta.ui.resourceUri binding
# 5. MCP resource exposure & MIME text/html;profile=mcp-app with CSP headers
# 6. Tool execution (tools/call) with Mcp-Method and Mcp-Name header mirroring
# 7. Progressive enhancement textual summaries in payload
# ==============================================================================

set -euo pipefail

BASE_URL="${MCP_URL:-http://localhost:8080}"
PROTO_VERSION="2025-11-25"

COLOR_GREEN="\033[0;32m"
COLOR_RED="\033[0;31m"
COLOR_CYAN="\033[0;36m"
COLOR_YELLOW="\033[0;33m"
COLOR_RESET="\033[0m"

PASS_COUNT=0
FAIL_COUNT=0

print_header() {
  echo -e "\n${COLOR_CYAN}==================================================================${COLOR_RESET}"
  echo -e "${COLOR_CYAN}  $1${COLOR_RESET}"
  echo -e "${COLOR_CYAN}==================================================================${COLOR_RESET}"
}

assert_success() {
  local desc="$1"
  local status="$2"
  local expected_status="${3:-200}"

  if [ "$status" -eq "$expected_status" ]; then
    echo -e "  [${COLOR_GREEN}PASS${COLOR_RESET}] $desc (HTTP $status)"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo -e "  [${COLOR_RED}FAIL${COLOR_RESET}] $desc: Expected HTTP $expected_status, got HTTP $status"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

assert_contains() {
  local desc="$1"
  local haystack="$2"
  local needle="$3"

  if echo "$haystack" | grep -Fq "$needle"; then
    echo -e "  [${COLOR_GREEN}PASS${COLOR_RESET}] $desc"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo -e "  [${COLOR_RED}FAIL${COLOR_RESET}] $desc: Pattern '$needle' not found"
    echo -e "         Snippet: $(echo "$haystack" | head -c 200)..."
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

echo -e "${COLOR_CYAN}Starting EchoCart Nexus E2E Integration Suite targeting: ${BASE_URL}${COLOR_RESET}"

# ------------------------------------------------------------------------------
# 1. Health & Readiness Endpoint
# ------------------------------------------------------------------------------
print_header "1. Health & Readiness Verification"
HEALTH_RESP=$(curl -s -w "\n%{http_code}" "${BASE_URL}/health")
HEALTH_BODY=$(echo "$HEALTH_RESP" | sed '$d')
HEALTH_CODE=$(echo "$HEALTH_RESP" | tail -n1)

assert_success "GET /health returns HTTP 200" "$HEALTH_CODE" 200
assert_contains "Health payload reports healthy status" "$HEALTH_BODY" '"status":"healthy"'
assert_contains "Health payload reports MCP protocol version" "$HEALTH_BODY" '"mcp_protocol_version":"2025-11-25"'

# ------------------------------------------------------------------------------
# 2. Protocol Header Enforcement
# ------------------------------------------------------------------------------
print_header "2. Wire Protocol Header Enforcement"

# Missing MCP-Protocol-Version must be rejected with 400
MISSING_RESP=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "ping"}')
MISSING_BODY=$(echo "$MISSING_RESP" | sed '$d')
MISSING_CODE=$(echo "$MISSING_RESP" | tail -n1)

assert_success "POST /mcp without MCP-Protocol-Version is rejected with 400" "$MISSING_CODE" 400
assert_contains "Error indicates missing protocol header" "$MISSING_BODY" "Invalid or missing MCP-Protocol-Version"

# Valid protocol version succeeds with 200
PING_RESP=$(curl -s -i -X POST "${BASE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: ${PROTO_VERSION}" \
  -H "Mcp-Method: ping" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "ping"}')

assert_contains "Ping response includes HTTP 200" "$PING_RESP" "200"
assert_contains "Ping response mirrors MCP-Protocol-Version header" "$PING_RESP" "MCP-Protocol-Version: 2025-11-25"
assert_contains "Ping response mirrors Mcp-Method header" "$PING_RESP" "Mcp-Method: ping"

# ------------------------------------------------------------------------------
# 3. Protocol Handshake (initialize)
# ------------------------------------------------------------------------------
print_header "3. JSON-RPC Handshake (initialize)"
INIT_RESP=$(curl -s -X POST "${BASE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: ${PROTO_VERSION}" \
  -H "Mcp-Method: initialize" \
  -d '{
    "jsonrpc": "2.0",
    "id": 10,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-11-25",
      "capabilities": {},
      "clientInfo": {"name": "E2E-Curl-Client", "version": "1.0.0"}
    }
  }')

assert_contains "Initialize response returns server capabilities" "$INIT_RESP" "protocolVersion"
assert_contains "Initialize response acknowledges server name" "$INIT_RESP" "EchoCart-Nexus-MCP"

# ------------------------------------------------------------------------------
# 4. Tool Discovery & MCP Apps Metadata Binding
# ------------------------------------------------------------------------------
print_header "4. Tool Discovery & MCP Apps Metadata Binding"
TOOLS_RESP=$(curl -s -X POST "${BASE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: ${PROTO_VERSION}" \
  -H "Mcp-Method: tools/list" \
  -d '{"jsonrpc": "2.0", "id": 20, "method": "tools/list"}')

assert_contains "tools/list returns manage_cart tool" "$TOOLS_RESP" '"name":"manage_cart"'
assert_contains "manage_cart binds _meta.ui.resourceUri = ui://echocart/cart-view.html" "$TOOLS_RESP" "ui://echocart/cart-view.html"
assert_contains "tools/list returns search_catalog tool" "$TOOLS_RESP" '"name":"search_catalog"'
assert_contains "search_catalog binds _meta.ui.resourceUri = ui://echocart/product-carousel.html" "$TOOLS_RESP" "ui://echocart/product-carousel.html"

# ------------------------------------------------------------------------------
# 5. Resources Listing & UI Template Reading
# ------------------------------------------------------------------------------
print_header "5. Resources Listing & UI Template Reading"
RES_LIST_RESP=$(curl -s -X POST "${BASE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: ${PROTO_VERSION}" \
  -H "Mcp-Method: resources/list" \
  -d '{"jsonrpc": "2.0", "id": 30, "method": "resources/list"}')

assert_contains "resources/list includes ui://echocart/cart-view.html" "$RES_LIST_RESP" "ui://echocart/cart-view.html"
assert_contains "Resource MIME type is text/html;profile=mcp-app" "$RES_LIST_RESP" "text/html;profile=mcp-app"
assert_contains "resources/list includes ui://echocart/product-carousel.html" "$RES_LIST_RESP" "ui://echocart/product-carousel.html"

# Read UI Template Resource
READ_RESP=$(curl -s -i -X POST "${BASE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: ${PROTO_VERSION}" \
  -H "Mcp-Method: resources/read" \
  -H "Mcp-Name: ui://echocart/cart-view.html" \
  -d '{
    "jsonrpc": "2.0",
    "id": 31,
    "method": "resources/read",
    "params": {"uri": "ui://echocart/cart-view.html"}
  }')

assert_contains "resources/read returns Content-Security-Policy header" "$READ_RESP" "Content-Security-Policy:"
assert_contains "resources/read returns cart-view HTML payload" "$READ_RESP" "EchoCart-Cart-View"

# ------------------------------------------------------------------------------
# 6. Tool Execution & Progressive Enhancement
# ------------------------------------------------------------------------------
print_header "6. Tool Execution & Progressive Enhancement"

# Search Catalog
SEARCH_CALL=$(curl -s -X POST "${BASE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: ${PROTO_VERSION}" \
  -H "Mcp-Method: tools/call" \
  -H "Mcp-Name: search_catalog" \
  -d '{
    "jsonrpc": "2.0",
    "id": 40,
    "method": "tools/call",
    "params": {
      "name": "search_catalog",
      "arguments": {"query": "headphones", "category": "audio"}
    }
  }')

assert_contains "search_catalog executes successfully" "$SEARCH_CALL" "ECHO-PRO-01"
assert_contains "search_catalog returns _meta.ui.resourceUri" "$SEARCH_CALL" "ui://echocart/product-carousel.html"
assert_contains "search_catalog includes natural-language voice summary" "$SEARCH_CALL" "matching product"

# Manage Cart (Add)
CART_CALL=$(curl -s -X POST "${BASE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: ${PROTO_VERSION}" \
  -H "Mcp-Method: tools/call" \
  -H "Mcp-Name: manage_cart" \
  -d '{
    "jsonrpc": "2.0",
    "id": 41,
    "method": "tools/call",
    "params": {
      "name": "manage_cart",
      "arguments": {
        "action": "add",
        "sku": "ECHO-PRO-01",
        "quantity": 1,
        "user_token": "usr_e2e_tester"
      }
    }
  }')

assert_contains "manage_cart returns success = true" "$CART_CALL" '"success": true'
assert_contains "manage_cart returns _meta.ui.resourceUri" "$CART_CALL" "ui://echocart/cart-view.html"
assert_contains "manage_cart includes voice summary" "$CART_CALL" "Cart updated"

# ------------------------------------------------------------------------------
# 7. Direct HTTP View Endpoints & CSP
# ------------------------------------------------------------------------------
print_header "7. Direct HTTP View Endpoints & CSP Verification"
CART_VIEW_HTTP=$(curl -s -i "${BASE_URL}/mcp-apps/cart-view.html")
assert_contains "GET /mcp-apps/cart-view.html returns HTTP 200" "$CART_VIEW_HTTP" "200"
assert_contains "GET /mcp-apps/cart-view.html serves text/html;profile=mcp-app" "$CART_VIEW_HTTP" "text/html;profile=mcp-app"
assert_contains "GET /mcp-apps/cart-view.html includes Content-Security-Policy" "$CART_VIEW_HTTP" "Content-Security-Policy:"

CAROUSEL_HTTP=$(curl -s -i "${BASE_URL}/mcp-apps/product-carousel.html")
assert_contains "GET /mcp-apps/product-carousel.html returns HTTP 200" "$CAROUSEL_HTTP" "200"
assert_contains "GET /mcp-apps/product-carousel.html includes Content-Security-Policy" "$CAROUSEL_HTTP" "Content-Security-Policy:"

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
print_header "E2E Test Execution Summary"
echo -e "  Total Passed: ${COLOR_GREEN}${PASS_COUNT}${COLOR_RESET}"
echo -e "  Total Failed: ${COLOR_RED}${FAIL_COUNT}${COLOR_RESET}"

if [ "$FAIL_COUNT" -eq 0 ]; then
  echo -e "\n${COLOR_GREEN}✓ ALL END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!${COLOR_RESET}\n"
  exit 0
else
  echo -e "\n${COLOR_RED}✗ SOME CHECKS FAILED.${COLOR_RESET}\n"
  exit 1
fi
