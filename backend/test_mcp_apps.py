"""
EchoCart Nexus - MCP Apps Extension (@modelcontextprotocol/ext-apps) Test Suite
Validates:
1. Server-Side Metadata Binding:
   - _meta.ui.resourceUri binding on tools/list and tools/call for manage_cart and search_catalog.
   - Exposing UI templates as MCP resources with MIME type text/html;profile=mcp-app and CSP metadata.
2. Content Security Policy (CSP) enforcement on HTTP responses and meta tags.
3. Bidirectional PostMessage protocol hooks and sandboxed HTML view integrity.
4. Progressive Enhancement: complete natural-language text summaries alongside UI resource pointers.
"""

import json
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.mcp_apps import (
    CART_VIEW_URI,
    PRODUCT_CAROUSEL_URI,
    MCP_APP_MIME_TYPE,
    CSP_HEADER_VALUE,
    DEFAULT_APP_CSP_METADATA,
    load_template,
)

REQUIRED_VERSION = "2025-11-25"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def parse_mcp_response(res):
    """Parses JSON-RPC payload from SSE text/event-stream or application/json."""
    content_type = res.headers.get("content-type", "")
    if "application/json" in content_type:
        return res.json()

    text = res.text
    for line in text.splitlines():
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            if data_str:
                return json.loads(data_str)
    return json.loads(text)


# ===========================================================================
# 1. Server-Side Metadata Binding Tests (tools/list & resources/list)
# ===========================================================================
def test_tools_list_contains_mcp_app_ui_metadata(client):
    """
    tools/list must advertise _meta.ui.resourceUri for manage_cart
    and search_catalog per the MCP Apps standard specification.
    """
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    tools = data["result"]["tools"]
    tool_map = {t["name"]: t for t in tools}

    # Verify manage_cart binding
    assert "manage_cart" in tool_map
    cart_tool = tool_map["manage_cart"]
    assert "_meta" in cart_tool, "manage_cart must include _meta block"
    assert "ui" in cart_tool["_meta"], "_meta must include 'ui' object"
    assert cart_tool["_meta"]["ui"]["resourceUri"] == CART_VIEW_URI

    # Verify search_catalog binding
    assert "search_catalog" in tool_map
    search_tool = tool_map["search_catalog"]
    assert "_meta" in search_tool, "search_catalog must include _meta block"
    assert "ui" in search_tool["_meta"], "_meta must include 'ui' object"
    assert search_tool["_meta"]["ui"]["resourceUri"] == PRODUCT_CAROUSEL_URI


def test_resources_list_exposes_mcp_app_templates(client):
    """
    resources/list must advertise both UI templates with:
    - MIME type text/html;profile=mcp-app
    - custom URI scheme ui://echocart/...
    - CSP metadata in _meta.ui.csp
    """
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    resources = data["result"]["resources"]
    res_map = {r["uri"]: r for r in resources}

    # Verify Cart View template resource
    assert CART_VIEW_URI in res_map
    cart_res = res_map[CART_VIEW_URI]
    assert cart_res["mimeType"] == MCP_APP_MIME_TYPE
    assert cart_res["name"] == "cart_view_template"
    assert "_meta" in cart_res and "ui" in cart_res["_meta"]
    assert "csp" in cart_res["_meta"]["ui"]
    assert "resourceDomains" in cart_res["_meta"]["ui"]["csp"]

    # Verify Product Carousel template resource
    assert PRODUCT_CAROUSEL_URI in res_map
    carousel_res = res_map[PRODUCT_CAROUSEL_URI]
    assert carousel_res["mimeType"] == MCP_APP_MIME_TYPE
    assert carousel_res["name"] == "product_carousel_template"
    assert "_meta" in carousel_res and "ui" in carousel_res["_meta"]
    assert "csp" in carousel_res["_meta"]["ui"]


def test_resources_read_cart_view_template(client):
    """
    resources/read for ui://echocart/cart-view.html returns valid HTML
    with proper MIME type and Content-Security-Policy header.
    """
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/read",
            "params": {"uri": CART_VIEW_URI},
        },
    )
    assert res.status_code == 200
    assert "Content-Security-Policy" in res.headers
    assert "default-src 'none'" in res.headers["Content-Security-Policy"]

    data = parse_mcp_response(res)
    contents = data["result"]["contents"]
    assert len(contents) >= 1
    content = contents[0]
    assert content["uri"] == CART_VIEW_URI
    assert content["mimeType"] == MCP_APP_MIME_TYPE
    assert "<!DOCTYPE html>" in content["text"]
    assert "EchoCart-Cart-View" in content["text"]


def test_resources_read_product_carousel_template(client):
    """
    resources/read for ui://echocart/product-carousel.html returns valid HTML
    with proper MIME type and Content-Security-Policy header.
    """
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {"uri": PRODUCT_CAROUSEL_URI},
        },
    )
    assert res.status_code == 200
    assert "Content-Security-Policy" in res.headers

    data = parse_mcp_response(res)
    contents = data["result"]["contents"]
    assert len(contents) >= 1
    content = contents[0]
    assert content["uri"] == PRODUCT_CAROUSEL_URI
    assert content["mimeType"] == MCP_APP_MIME_TYPE
    assert "<!DOCTYPE html>" in content["text"]
    assert "EchoCart-Product-Carousel" in content["text"]


# ===========================================================================
# 2. Tool Execution Return Schema & Progressive Enhancement Tests
# ===========================================================================
def test_manage_cart_tool_execution_metadata_and_progressive_enhancement(client):
    """
    tools/call for manage_cart returns:
    1. _meta.ui.resourceUri pointing to ui://echocart/cart-view.html
    2. content[0]: Parseable JSON structured payload
    3. content[1]: Complete natural-language voice summary for screenless clients
    """
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "manage_cart",
                "arguments": {
                    "action": "add",
                    "sku": "ECHO-PRO-01",
                    "quantity": 1,
                    "user_token": "usr_alexa_test",
                },
            },
        },
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    result = data["result"]

    # Verify UI metadata
    assert "_meta" in result, "Tool result must include _meta"
    assert "ui" in result["_meta"], "_meta must include 'ui'"
    assert result["_meta"]["ui"]["resourceUri"] == CART_VIEW_URI

    # Verify Content & Progressive Enhancement
    contents = result["content"]
    assert len(contents) >= 2, "Must return structured data + natural language textual summary"

    # content[0] is JSON
    structured_json = json.loads(contents[0]["text"])
    assert structured_json["success"] is True
    assert structured_json["action"] == "add"
    assert structured_json["cart"]["total_items"] >= 1

    # content[1] is natural language voice summary
    voice_summary = contents[1]["text"]
    assert "Cart updated" in voice_summary
    assert "ECHO-PRO-01" in voice_summary


def test_search_catalog_tool_execution_metadata_and_progressive_enhancement(client):
    """
    tools/call for search_catalog returns:
    1. _meta.ui.resourceUri pointing to ui://echocart/product-carousel.html
    2. content[0]: Parseable JSON structured product list
    3. content[1]: Complete natural-language voice summary
    """
    res = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": REQUIRED_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "search_catalog",
                "arguments": {"query": "headphones"},
            },
        },
    )
    assert res.status_code == 200
    data = parse_mcp_response(res)
    result = data["result"]

    # Verify UI metadata
    assert "_meta" in result
    assert result["_meta"]["ui"]["resourceUri"] == PRODUCT_CAROUSEL_URI

    # Verify Progressive Enhancement
    contents = result["content"]
    assert len(contents) >= 2
    items = json.loads(contents[0]["text"])
    assert isinstance(items, list)
    assert len(items) >= 1

    voice_summary = contents[1]["text"]
    assert "Found" in voice_summary
    assert "matching product" in voice_summary


# ===========================================================================
# 3. HTTP Template Serving & CSP Headers Tests
# ===========================================================================
def test_http_endpoint_serves_cart_view_with_csp(client):
    """GET /mcp-apps/cart-view.html returns 200 with text/html;profile=mcp-app and CSP."""
    res = client.get("/mcp-apps/cart-view.html")
    assert res.status_code == 200
    content_type = res.headers.get("content-type", "")
    assert "text/html" in content_type
    assert "profile=mcp-app" in content_type
    assert "Content-Security-Policy" in res.headers
    assert "default-src 'none'" in res.headers["Content-Security-Policy"]
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert "<title>EchoCart Nexus - Smart Cart Card</title>" in res.text


def test_http_endpoint_serves_product_carousel_with_csp(client):
    """GET /mcp-apps/product-carousel.html returns 200 with text/html;profile=mcp-app and CSP."""
    res = client.get("/mcp-apps/product-carousel.html")
    assert res.status_code == 200
    content_type = res.headers.get("content-type", "")
    assert "text/html" in content_type
    assert "profile=mcp-app" in content_type
    assert "Content-Security-Policy" in res.headers
    assert "default-src 'none'" in res.headers["Content-Security-Policy"]
    assert "<title>EchoCart Nexus - Smart Product Carousel</title>" in res.text


def test_http_endpoint_serves_alexa_simulator(client):
    """GET /mcp-apps and /mcp-apps/ return 200 with Alexa simulator host page."""
    res = client.get("/mcp-apps")
    assert res.status_code == 200
    assert "EchoCart" in res.text
    assert "Alexa+ Smart Display" in res.text
    assert "<iframe" in res.text


def test_http_endpoint_404_for_unknown_template(client):
    """GET /mcp-apps/nonexistent.html returns 404."""
    res = client.get("/mcp-apps/nonexistent.html")
    assert res.status_code == 404


# ===========================================================================
# 4. Sandboxed HTML & PostMessage Bridge Integrity Tests
# ===========================================================================
def test_cart_view_template_integrity():
    """Validates cart-view.html structure and postMessage bridge compliance."""
    html = load_template("cart-view.html")

    # CSP meta tag present
    assert '<meta http-equiv="Content-Security-Policy"' in html
    assert "default-src 'none'" in html
    assert "script-src 'unsafe-inline'" in html

    # PostMessage bridge hooks present
    assert "ui/initialize" in html
    assert "ui/tool-result" in html
    assert "tools/call" in html
    assert "manage_cart" in html

    # UI Components present
    assert "stepper-btn" in html
    assert "item-thumbnail" in html
    assert "summary-row total" in html
    assert "Voice Checkout" in html


def test_product_carousel_template_integrity():
    """Validates product-carousel.html structure and postMessage bridge compliance."""
    html = load_template("product-carousel.html")

    # CSP meta tag present
    assert '<meta http-equiv="Content-Security-Policy"' in html
    assert "default-src 'none'" in html

    # PostMessage bridge hooks present
    assert "ui/initialize" in html
    assert "ui/tool-result" in html
    assert "tools/call" in html
    assert "manage_cart" in html

    # UI Components present
    assert "slider-viewport" in html
    assert "product-card" in html
    assert "btn-add-cart" in html
    assert "category-badge" in html
    assert "filter-chip" in html
