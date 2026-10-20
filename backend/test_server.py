"""
EchoCart Nexus MCP Server - Comprehensive Test Suite
Validates:
1. Strict MCP-Protocol-Version: 2025-11-25 header enforcement.
2. Origin header validation and HTTP 403 Forbidden gating for untrusted origins.
3. Mcp-Method and Mcp-Name header validation and mirroring against JSON-RPC 2.0 payloads.
4. Core MCP Tools: search_catalog, manage_cart, get_order_status.
5. Core MCP Resources: resource://store/promotions/current, resource://store/policies/returns.
6. Core MCP Prompts: checkout_assistant.
7. Standard MCP wire methods: initialize, tools/list, resources/list, prompts/list, ping.
"""

import json
import pytest
from starlette.testclient import TestClient
from backend.main import app, MCPWireProtocolMiddleware, Starlette, mcp_sub_app

REQUIRED_VERSION = "2025-11-25"


# ---------------------------------------------------------------------------
# Helper fixture for standard test client
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def restricted_client():
    """Client with strict origin whitelist for testing Origin 403 checks."""
    restricted_app = Starlette(lifespan=mcp_sub_app.lifespan)
    restricted_app.add_middleware(
        MCPWireProtocolMiddleware,
        allowed_origins=["https://trusted.echocart.com", "http://localhost:3000"]
    )
    restricted_app.mount("", mcp_sub_app)
    with TestClient(restricted_app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Helper: Parse Streamable HTTP / SSE or JSON response
# ---------------------------------------------------------------------------
def parse_mcp_response(res):
    """Parses JSON-RPC payload from either text/event-stream (SSE) or application/json."""
    content_type = res.headers.get("content-type", "")
    if "application/json" in content_type:
        return res.json()
    
    text = res.text
    for line in text.splitlines():
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            if data_str:
                return json.loads(data_str)
    
    # Fallback to direct json parse
    return json.loads(text)


# ===========================================================================
# 1. Wire Protocol & Version Enforcement Tests
# ===========================================================================
def test_missing_protocol_version_header_rejected(client):
    """POST /mcp without MCP-Protocol-Version must return HTTP 400."""
    res = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
    )
    assert res.status_code == 400
    data = res.json()
    assert "error" in data
    assert "Invalid or missing MCP-Protocol-Version header" in data["error"]["message"]
    assert res.headers.get("mcp-protocol-version") == REQUIRED_VERSION


def test_invalid_protocol_version_header_rejected(client):
    """POST /mcp with non-2025-11-25 version must return HTTP 400."""
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": "2024-11-05"},
        json={"jsonrpc": "2.0", "id": 2, "method": "ping"}
    )
    assert res.status_code == 400
    data = res.json()
    assert "error" in data
    assert "Expected '2025-11-25'" in data["error"]["message"]


def test_valid_protocol_version_accepted(client):
    """POST /mcp with MCP-Protocol-Version: 2025-11-25 succeeds."""
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={"jsonrpc": "2.0", "id": 3, "method": "ping"}
    )
    assert res.status_code == 200
    assert res.headers.get("mcp-protocol-version") == REQUIRED_VERSION
    data = parse_mcp_response(res)
    assert data.get("id") == 3
    assert data.get("result") == {}


# ===========================================================================
# 2. Origin & CORS Security Gating Tests
# ===========================================================================
def test_untrusted_origin_returns_403_forbidden(restricted_client):
    """Untrusted Origin must be rejected with HTTP 403 Forbidden."""
    res = restricted_client.post(
        "/mcp",
        headers={
            "Origin": "https://malicious-phishing-site.com",
            "MCP-Protocol-Version": REQUIRED_VERSION,
        },
        json={"jsonrpc": "2.0", "id": 4, "method": "ping"}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["error"] == "Forbidden: Untrusted Origin"


def test_trusted_origin_allowed(restricted_client):
    """Trusted Origin is accepted and returns Access-Control-Allow-Origin."""
    res = restricted_client.post(
        "/mcp",
        headers={
            "Origin": "https://trusted.echocart.com",
            "MCP-Protocol-Version": REQUIRED_VERSION,
        },
        json={"jsonrpc": "2.0", "id": 5, "method": "ping"}
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://trusted.echocart.com"


def test_cors_preflight_options_response(client):
    """OPTIONS request returns 204 and includes proper CORS & exposed headers."""
    res = client.options(
        "/mcp",
        headers={"Origin": "https://any-domain.com"}
    )
    assert res.status_code == 204
    assert res.headers.get("access-control-allow-origin") == "https://any-domain.com"
    assert "MCP-Protocol-Version" in res.headers.get("access-control-allow-headers", "")
    assert "Mcp-Method" in res.headers.get("access-control-allow-headers", "")
    assert "Mcp-Name" in res.headers.get("access-control-allow-headers", "")
    assert "MCP-Protocol-Version" in res.headers.get("access-control-expose-headers", "")


# ===========================================================================
# 3. Mcp-Method and Mcp-Name Header Validation & Mirroring
# ===========================================================================
def test_mcp_method_mismatch_returns_400(client):
    """If Mcp-Method does not match payload method, reject with HTTP 400."""
    res = client.post(
        "/mcp",
        headers={
            "MCP-Protocol-Version": REQUIRED_VERSION,
            "Mcp-Method": "tools/call",  # mismatched header vs body 'ping'
        },
        json={"jsonrpc": "2.0", "id": 6, "method": "ping"}
    )
    assert res.status_code == 400
    data = res.json()
    assert "Mcp-Method header mismatch" in data["error"]["message"]


def test_mcp_name_mismatch_returns_400(client):
    """If Mcp-Name does not match payload target name, reject with HTTP 400."""
    res = client.post(
        "/mcp",
        headers={
            "MCP-Protocol-Version": REQUIRED_VERSION,
            "Mcp-Method": "tools/call",
            "Mcp-Name": "wrong_tool_name",
        },
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "search_catalog", "arguments": {"query": "headphones"}}
        }
    )
    assert res.status_code == 400
    data = res.json()
    assert "Mcp-Name header mismatch" in data["error"]["message"]


def test_mcp_method_and_name_mirroring_in_response(client):
    """Valid request mirrors Mcp-Method and Mcp-Name in response headers."""
    res = client.post(
        "/mcp",
        headers={
            "MCP-Protocol-Version": REQUIRED_VERSION,
            "Mcp-Method": "tools/call",
            "Mcp-Name": "search_catalog",
        },
        json={
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "search_catalog", "arguments": {"query": "headphones"}}
        }
    )
    assert res.status_code == 200
    assert res.headers.get("mcp-protocol-version") == REQUIRED_VERSION
    assert res.headers.get("mcp-method") == "tools/call"
    assert res.headers.get("mcp-name") == "search_catalog"


# ===========================================================================
# 4. Core MCP Tools: search_catalog, manage_cart, get_order_status
# ===========================================================================
def test_tool_search_catalog(client):
    """Test search_catalog tool with query and category filtering."""
    # 1. Search by keyword
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "search_catalog",
                "arguments": {"query": "Noise-Cancelling"}
            }
        }
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    assert not data.get("error")
    tool_result = data["result"]
    assert tool_result["isError"] is False
    content_raw = tool_result["content"][0]["text"]
    items = json.loads(content_raw)
    assert len(items) >= 1
    assert items[0]["sku"] == "ECHO-PRO-01"
    assert "Headphones" in items[0]["title"]
    assert items[0]["price"] == 249.99
    assert items[0]["stock"] == 42
    assert items[0]["ratings"] == 4.8

    # 2. Search with category filter
    res_cat = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "search_catalog",
                "arguments": {"query": "", "category": "audio"}
            }
        }
    )
    assert res_cat.status_code == 200
    data_cat = parse_mcp_response(res_cat)
    audio_items = json.loads(data_cat["result"]["content"][0]["text"])
    assert all(item["category"] == "audio" for item in audio_items)


def test_tool_manage_cart_lifecycle(client):
    """Test cart lifecycle: add, update, remove, and structured summary."""
    token = "test_user_session_42"

    # Step 1: Add item to cart
    res_add = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "manage_cart",
                "arguments": {
                    "action": "add",
                    "sku": "ECHO-PRO-01",
                    "quantity": 2,
                    "user_token": token,
                }
            }
        }
    )
    assert res_add.status_code == 200
    data_add = parse_mcp_response(res_add)
    cart_resp = json.loads(data_add["result"]["content"][0]["text"])
    assert cart_resp["success"] is True
    assert cart_resp["action"] == "add"
    assert cart_resp["cart"]["total_items"] == 2
    assert cart_resp["cart"]["total_price"] == round(249.99 * 2, 2)

    # Step 2: Update item quantity
    res_upd = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "manage_cart",
                "arguments": {
                    "action": "update",
                    "sku": "ECHO-PRO-01",
                    "quantity": 1,
                    "user_token": token,
                }
            }
        }
    )
    assert res_upd.status_code == 200
    data_upd = parse_mcp_response(res_upd)
    cart_resp_upd = json.loads(data_upd["result"]["content"][0]["text"])
    assert cart_resp_upd["cart"]["total_items"] == 1
    assert cart_resp_upd["cart"]["total_price"] == 249.99

    # Step 3: Remove item
    res_rem = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {
                "name": "manage_cart",
                "arguments": {
                    "action": "remove",
                    "sku": "ECHO-PRO-01",
                    "quantity": 0,
                    "user_token": token,
                }
            }
        }
    )
    assert res_rem.status_code == 200
    data_rem = parse_mcp_response(res_rem)
    cart_resp_rem = json.loads(data_rem["result"]["content"][0]["text"])
    assert cart_resp_rem["cart"]["total_items"] == 0
    assert cart_resp_rem["cart"]["total_price"] == 0.0

    # Step 4: Invalid action test
    res_inv = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 23,
            "method": "tools/call",
            "params": {
                "name": "manage_cart",
                "arguments": {
                    "action": "invalid_action",
                    "sku": "ECHO-PRO-01",
                    "quantity": 1,
                    "user_token": token,
                }
            }
        }
    )
    assert res_inv.status_code == 200
    data_inv = parse_mcp_response(res_inv)
    cart_resp_inv = json.loads(data_inv["result"]["content"][0]["text"])
    assert cart_resp_inv["success"] is False
    assert "Invalid action" in cart_resp_inv["error"]


def test_tool_get_order_status(client):
    """Test get_order_status with known order ID and fallback."""
    # 1. Existing order
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "get_order_status",
                "arguments": {
                    "order_id": "ORD-98241",
                    "user_token": "usr_token_alpha",
                }
            }
        }
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    order_data = json.loads(data["result"]["content"][0]["text"])
    assert order_data["order_id"] == "ORD-98241"
    assert order_data["status"] == "out_for_delivery"
    assert order_data["carrier"] == "FedEx Express"
    assert len(order_data["timeline"]) >= 3

    # 2. Dynamic fallback for new order
    res_fallback = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {
                "name": "get_order_status",
                "arguments": {
                    "order_id": "ORD-NEW-9999",
                    "user_token": "usr_token_unknown",
                }
            }
        }
    )
    assert res_fallback.status_code == 200
    data_fb = parse_mcp_response(res_fallback)
    order_fb = json.loads(data_fb["result"]["content"][0]["text"])
    assert order_fb["order_id"] == "ORD-NEW-9999"
    assert order_fb["status"] == "processing"


# ===========================================================================
# 5. Core MCP Resources: promotions and returns policy
# ===========================================================================
def test_resource_promotions_current(client):
    """Test reading static JSON resource for active discount codes."""
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 40,
            "method": "resources/read",
            "params": {"uri": "resource://store/promotions/current"}
        }
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    contents = data["result"]["contents"]
    assert len(contents) == 1
    assert contents[0]["uri"] == "resource://store/promotions/current"
    promo_data = json.loads(contents[0]["text"])
    assert "promotions" in promo_data
    codes = [p["code"] for p in promo_data["promotions"]]
    assert "NEXUS20" in codes
    assert "VOICEFIRST" in codes
    assert "FREESHIP" in codes


def test_resource_policies_returns(client):
    """Test reading text returns policy guidelines resource."""
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 41,
            "method": "resources/read",
            "params": {"uri": "resource://store/policies/returns"}
        }
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    contents = data["result"]["contents"]
    assert len(contents) == 1
    assert contents[0]["uri"] == "resource://store/policies/returns"
    assert "30-Day Hassle-Free Returns" in contents[0]["text"]


# ===========================================================================
# 6. Core MCP Prompts: checkout_assistant
# ===========================================================================
def test_prompt_checkout_assistant(client):
    """Test retrieving checkout_assistant voice shopping assistant template."""
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 50,
            "method": "prompts/get",
            "params": {"name": "checkout_assistant"}
        }
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    messages = data["result"]["messages"]
    assert len(messages) >= 1
    msg_text = messages[0]["content"]["text"]
    assert "EchoCart Voice Assistant" in msg_text
    assert "voice-first" in msg_text.lower()


# ===========================================================================
# 7. Standard MCP Initialization & Discovery
# ===========================================================================
def test_mcp_initialize_and_discovery(client):
    """Test standard MCP protocol initialize, tools/list, resources/list, prompts/list."""
    # 1. Initialize
    res_init = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 60,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "EchoCart-TestRunner", "version": "1.0.0"}
            }
        }
    )
    assert res_init.status_code == 200
    init_data = parse_mcp_response(res_init)["result"]
    assert "tools" in init_data["capabilities"]
    assert "resources" in init_data["capabilities"]
    assert "prompts" in init_data["capabilities"]

    # 2. tools/list
    res_tools = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={"jsonrpc": "2.0", "id": 61, "method": "tools/list"}
    )
    assert res_tools.status_code == 200
    tool_names = [t["name"] for t in parse_mcp_response(res_tools)["result"]["tools"]]
    assert "search_catalog" in tool_names
    assert "manage_cart" in tool_names
    assert "get_order_status" in tool_names

    # 3. resources/list
    res_res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={"jsonrpc": "2.0", "id": 62, "method": "resources/list"}
    )
    assert res_res.status_code == 200
    res_uris = [r["uri"] for r in parse_mcp_response(res_res)["result"]["resources"]]
    assert "resource://store/promotions/current" in res_uris
    assert "resource://store/policies/returns" in res_uris

    # 4. prompts/list
    res_prompts = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={"jsonrpc": "2.0", "id": 63, "method": "prompts/list"}
    )
    assert res_prompts.status_code == 200
    prompt_names = [p["name"] for p in parse_mcp_response(res_prompts)["result"]["prompts"]]
    assert "checkout_assistant" in prompt_names


# ===========================================================================
# 8. Health Endpoint
# ===========================================================================
def test_health_check_endpoint(client):
    """GET /health provides AWS Lambda Web Adapter readiness verification."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["server"] == "EchoCart-Nexus-MCP"
    assert data["mcp_protocol_version"] == REQUIRED_VERSION
    assert data["stateless_http"] is True


if __name__ == "__main__":
    pytest.main(["-v", __file__])
