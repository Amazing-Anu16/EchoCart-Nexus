"""
EchoCart Nexus - Production-Grade Model Context Protocol (MCP) Server
Adhering to the 2025-11-25 Streamable HTTP Specification.
Optimized for Serverless Deployment on AWS Lambda via AWS Lambda Web Adapter.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import mcp.types as types
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

try:
    from backend.mcp_apps import (
        CART_VIEW_URI,
        PRODUCT_CAROUSEL_URI,
        MCP_APP_MIME_TYPE,
        CSP_HEADER_VALUE,
        create_call_tool_result,
        register_mcp_apps_resources,
        mount_mcp_apps_http,
    )
except ImportError:
    from mcp_apps import (
        CART_VIEW_URI,
        PRODUCT_CAROUSEL_URI,
        MCP_APP_MIME_TYPE,
        CSP_HEADER_VALUE,
        create_call_tool_result,
        register_mcp_apps_resources,
        mount_mcp_apps_http,
    )


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("echocart_mcp")

# ---------------------------------------------------------------------------
# Protocol Constants & Configuration
# ---------------------------------------------------------------------------
REQUIRED_MCP_PROTOCOL_VERSION = "2025-11-25"
ENV_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [origin.strip() for origin in ENV_ALLOWED_ORIGINS.split(",") if origin.strip()]

# ---------------------------------------------------------------------------
# In-Memory Catalog & State Datastores (Production-Mock Datastores)
# ---------------------------------------------------------------------------
CATALOG_DATA = [
    {
        "sku": "ECHO-PRO-01",
        "title": "EchoCart Nexus Pro Active Noise-Cancelling Headphones",
        "category": "audio",
        "price": 249.99,
        "stock": 42,
        "ratings": 4.8,
        "description": "Ultra-low latency wireless audio with spatial voice pickup and hybrid ANC.",
    },
    {
        "sku": "ECHO-EAR-02",
        "title": "EchoCart TrueWireless Spatial Earbuds",
        "category": "audio",
        "price": 129.99,
        "stock": 78,
        "ratings": 4.6,
        "description": "Compact IPX7 waterproof earbuds with voice command wake-word optimization.",
    },
    {
        "sku": "ECHO-SPK-03",
        "title": "EchoCart Nexus Smart Soundbar & Hub",
        "category": "home",
        "price": 349.00,
        "stock": 18,
        "ratings": 4.9,
        "description": "Voice-first smart sound system with dual subwoofers and integrated smart assistant hub.",
    },
    {
        "sku": "ECHO-MIC-04",
        "title": "EchoCart VoiceStream Studio Microphone",
        "category": "electronics",
        "price": 89.50,
        "stock": 115,
        "ratings": 4.7,
        "description": "Broadcast-quality cardioid condenser USB microphone with real-time hardware gain filter.",
    },
    {
        "sku": "ECHO-PWR-05",
        "title": "EchoCart MagCharge 65W Wireless Multi-Device Pad",
        "category": "electronics",
        "price": 59.99,
        "stock": 150,
        "ratings": 4.5,
        "description": "3-in-1 fast wireless charging station with GaN thermal architecture.",
    },
    {
        "sku": "ECHO-WCH-06",
        "title": "EchoCart Nexus Kinetic Smartwatch",
        "category": "wearables",
        "price": 199.95,
        "stock": 60,
        "ratings": 4.7,
        "description": "AMOLED touch display, biometrics, offline voice checkout authentication.",
    },
]

# In-memory Cart Store: keyed by user_token -> {sku: quantity}
CART_STORE: Dict[str, Dict[str, int]] = {}

# Mock Orders Store
ORDER_STORE: Dict[str, Dict[str, Any]] = {
    "ORD-98241": {
        "order_id": "ORD-98241",
        "user_token": "usr_token_alpha",
        "status": "out_for_delivery",
        "carrier": "FedEx Express",
        "tracking_number": "FX-889123014",
        "estimated_delivery": "2026-10-21T18:00:00Z",
        "items": [
            {"sku": "ECHO-PRO-01", "title": "EchoCart Nexus Pro Headphones", "quantity": 1, "unit_price": 249.99}
        ],
        "timeline": [
            {"status": "order_placed", "timestamp": "2026-10-19T09:15:00Z", "location": "Online"},
            {"status": "shipped", "timestamp": "2026-10-20T04:30:00Z", "location": "Memvis Logistics Hub, TN"},
            {"status": "out_for_delivery", "timestamp": "2026-10-21T07:45:00Z", "location": "Local Carrier Facility"},
        ],
    },
    "ORD-54129": {
        "order_id": "ORD-54129",
        "user_token": "usr_token_beta",
        "status": "shipped",
        "carrier": "DHL Global Express",
        "tracking_number": "DHL-440192837",
        "estimated_delivery": "2026-10-23T14:30:00Z",
        "items": [
            {"sku": "ECHO-EAR-02", "title": "EchoCart TrueWireless Spatial Earbuds", "quantity": 2, "unit_price": 129.99}
        ],
        "timeline": [
            {"status": "order_placed", "timestamp": "2026-10-20T11:00:00Z", "location": "Online"},
            {"status": "shipped", "timestamp": "2026-10-20T22:15:00Z", "location": "Eindhoven Logistics Center"},
        ],
    },
}

# ---------------------------------------------------------------------------
# FastMCP Server Initialization
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="EchoCart-Nexus-MCP",
    instructions="Voice-first intelligent commerce and fulfillment MCP server for EchoCart Nexus.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Core MCP Primitives: Tools
# ---------------------------------------------------------------------------
@mcp.tool(
    name="search_catalog",
    description="Search products in the catalog by keyword query and optional category filter.",
    meta={"ui": {"resourceUri": PRODUCT_CAROUSEL_URI}},
)
def search_catalog(query: str, category: Optional[str] = None) -> types.CallToolResult:
    """Search catalog records. Returns structured product records: SKU, title, price, stock, ratings."""
    logger.info(f"Executing search_catalog: query={query!r}, category={category!r}")
    q_norm = query.strip().lower()
    cat_norm = category.strip().lower() if category else None

    results = []
    for item in CATALOG_DATA:
        # Category match
        if cat_norm and item["category"].lower() != cat_norm:
            continue

        # Query match over title, description, sku, category
        searchable_text = f"{item['title']} {item['sku']} {item['category']} {item['description']}".lower()
        if not q_norm or q_norm in searchable_text:
            results.append({
                "sku": item["sku"],
                "title": item["title"],
                "price": item["price"],
                "stock": item["stock"],
                "ratings": item["ratings"],
                "category": item["category"],
            })

    # Progressive enhancement natural language voice summary
    if results:
        items_preview = ", ".join([f"{item['title']} (${item['price']:.2f})" for item in results[:3]])
        voice_summary = f"Found {len(results)} matching product{'s' if len(results) > 1 else ''}: {items_preview}."
    else:
        voice_summary = f"No products found matching query '{query}'."

    return create_call_tool_result(
        structured_data=results,
        resource_uri=PRODUCT_CAROUSEL_URI,
        text_summary=voice_summary,
    )


@mcp.tool(
    name="manage_cart",
    description="Manage user shopping cart state: add, update, or remove items by SKU.",
    meta={"ui": {"resourceUri": CART_VIEW_URI}},
)
def manage_cart(action: str, sku: str, quantity: int, user_token: str) -> types.CallToolResult:
    """Manages cart state (add/remove/update) with structured returns."""
    logger.info(f"Executing manage_cart: action={action}, sku={sku}, quantity={quantity}, user={user_token}")
    action_norm = action.strip().lower()
    if action_norm not in ("add", "remove", "update"):
        err_payload = {
            "success": False,
            "error": f"Invalid action: {action!r}. Supported actions are: 'add', 'remove', 'update'.",
            "user_token": user_token,
            "cart": {"items": [], "total_items": 0, "total_price": 0.0},
        }
        return create_call_tool_result(
            structured_data=err_payload,
            resource_uri=CART_VIEW_URI,
            text_summary=f"Cart update failed: Invalid action {action!r}.",
            is_error=False,
        )

    if not user_token or not user_token.strip():
        err_payload = {
            "success": False,
            "error": "user_token cannot be empty.",
            "user_token": "",
            "cart": {"items": [], "total_items": 0, "total_price": 0.0},
        }
        return create_call_tool_result(
            structured_data=err_payload,
            resource_uri=CART_VIEW_URI,
            text_summary="Cart update failed: user_token cannot be empty.",
            is_error=False,
        )

    # Verify SKU exists in catalog
    sku_normalized = sku.strip().upper()
    catalog_item = next((item for item in CATALOG_DATA if item["sku"].upper() == sku_normalized), None)
    if not catalog_item and action_norm != "remove":
        err_payload = {
            "success": False,
            "error": f"Product with SKU '{sku}' not found in catalog.",
            "user_token": user_token,
            "cart": _compute_cart_summary(user_token),
        }
        return create_call_tool_result(
            structured_data=err_payload,
            resource_uri=CART_VIEW_URI,
            text_summary=f"Cart update failed: Product SKU '{sku}' not found in catalog.",
            is_error=False,
        )

    user_cart = CART_STORE.setdefault(user_token, {})

    if action_norm == "add":
        if quantity <= 0:
            err_payload = {
                "success": False,
                "error": "Quantity to add must be greater than 0.",
                "user_token": user_token,
                "cart": _compute_cart_summary(user_token),
            }
            return create_call_tool_result(
                structured_data=err_payload,
                resource_uri=CART_VIEW_URI,
                text_summary="Cart update failed: Quantity must be greater than 0.",
                is_error=False,
            )
        current_qty = user_cart.get(sku_normalized, 0)
        user_cart[sku_normalized] = current_qty + quantity

    elif action_norm == "update":
        if quantity <= 0:
            # Updating to 0 or less removes the item
            user_cart.pop(sku_normalized, None)
        else:
            user_cart[sku_normalized] = quantity

    elif action_norm == "remove":
        user_cart.pop(sku_normalized, None)

    summary = _compute_cart_summary(user_token)
    success_payload = {
        "success": True,
        "action": action_norm,
        "user_token": user_token,
        "cart": summary,
        "message": f"Successfully performed '{action_norm}' for SKU {sku_normalized}."
    }
    voice_summary = (
        f"Cart updated: {action_norm.title()} {sku_normalized}. "
        f"You now have {summary['total_items']} items in your cart totaling ${summary['total_price']:.2f}."
    )
    return create_call_tool_result(
        structured_data=success_payload,
        resource_uri=CART_VIEW_URI,
        text_summary=voice_summary,
        is_error=False,
    )


def _compute_cart_summary(user_token: str) -> Dict[str, Any]:
    """Helper to compute structured cart summary."""
    user_cart = CART_STORE.get(user_token, {})
    items = []
    total_price = 0.0
    total_items = 0

    catalog_map = {item["sku"].upper(): item for item in CATALOG_DATA}

    for sku_key, qty in user_cart.items():
        cat_info = catalog_map.get(sku_key)
        unit_price = cat_info["price"] if cat_info else 0.0
        title = cat_info["title"] if cat_info else "Unknown SKU"
        subtotal = round(unit_price * qty, 2)
        total_price += subtotal
        total_items += qty

        items.append({
            "sku": sku_key,
            "title": title,
            "quantity": qty,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })

    return {
        "items": items,
        "total_items": total_items,
        "total_price": round(total_price, 2),
    }


@mcp.tool(
    name="get_order_status",
    description="Retrieve delivery timelines, fulfillment status, and tracking info for an order.",
)
def get_order_status(order_id: str, user_token: str) -> Dict[str, Any]:
    """Returns delivery timelines, status, and tracking info."""
    logger.info(f"Executing get_order_status: order_id={order_id}, user={user_token}")
    oid = order_id.strip()
    order = ORDER_STORE.get(oid)

    if order:
        return {
            "found": True,
            "order_id": order["order_id"],
            "status": order["status"],
            "carrier": order["carrier"],
            "tracking_number": order["tracking_number"],
            "estimated_delivery": order["estimated_delivery"],
            "items": order["items"],
            "timeline": order["timeline"],
        }

    # Generate realistic dynamic fallback tracking for unrecognized orders
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "found": True,
        "order_id": oid,
        "status": "processing",
        "carrier": "Standard Fulfillment Network",
        "tracking_number": f"TRK-{abs(hash(oid)) % 1000000000:09d}",
        "estimated_delivery": "Within 3-5 business days",
        "items": [],
        "timeline": [
            {"status": "order_confirmed", "timestamp": now_iso, "location": "Nexus Fulfillment Core"},
            {"status": "preparing_shipment", "timestamp": now_iso, "location": "Warehouse Center"},
        ],
    }


# ---------------------------------------------------------------------------
# Core MCP Primitives: Resources
# ---------------------------------------------------------------------------
@mcp.resource(
    uri="resource://store/promotions/current",
    name="current_promotions",
    description="Active store discount codes and ongoing seasonal promotions.",
    mime_type="application/json",
)
def get_current_promotions() -> str:
    """Static JSON with active discount codes."""
    promotions_payload = {
        "store": "EchoCart Nexus",
        "last_updated": "2026-10-21T00:00:00Z",
        "promotions": [
            {
                "code": "NEXUS20",
                "discount_type": "percentage",
                "discount_value": 20,
                "description": "20% off all audio and smart wearable hardware",
                "minimum_order": 99.00,
                "expires_at": "2026-12-31T23:59:59Z",
                "is_active": True,
            },
            {
                "code": "VOICEFIRST",
                "discount_type": "fixed_amount",
                "discount_value": 15.00,
                "description": "$15 off any voice assistant or studio accessory",
                "minimum_order": 50.00,
                "expires_at": "2026-12-31T23:59:59Z",
                "is_active": True,
            },
            {
                "code": "FREESHIP",
                "discount_type": "free_shipping",
                "discount_value": 0,
                "description": "Free standard expedited shipping on all orders",
                "minimum_order": 0.00,
                "expires_at": "2026-12-31T23:59:59Z",
                "is_active": True,
            },
        ],
    }
    return json.dumps(promotions_payload, indent=2)


@mcp.resource(
    uri="resource://store/policies/returns",
    name="returns_policy",
    description="Official return and warranty guidelines for EchoCart Nexus.",
    mime_type="text/plain",
)
def get_returns_policy() -> str:
    """Text returns policy guidelines."""
    return (
        "EchoCart Nexus Official Return & Warranty Policy:\n\n"
        "1. 30-Day Hassle-Free Returns: Any unopened or like-new hardware can be returned within 30 days "
        "of receipt for a full refund to the original payment method.\n"
        "2. Prepaid Shipping: Return labels are complimentary. Initiate a return via voice or the app "
        "to generate an instant QR code or printable label.\n"
        "3. Warranty Coverage: All EchoCart Nexus hardware is protected by a 1-year limited hardware warranty "
        "covering manufacturing defects and acoustic hardware failures.\n"
        "4. Inspection & Refund Timeline: Refunds are inspected and approved within 48 business hours of receipt at "
        "our regional return hub."
    )


# ---------------------------------------------------------------------------
# Core MCP Primitives: Prompts
# ---------------------------------------------------------------------------
@mcp.prompt(
    name="checkout_assistant",
    description="Conversational system template instructing the LLM to act as a concise voice-first shopping assistant.",
)
def checkout_assistant() -> str:
    """Conversational system template instructing the LLM to act as a concise voice-first shopping assistant."""
    return (
        "You are EchoCart Voice Assistant, a voice-first intelligent shopping agent for EchoCart Nexus. "
        "You are speaking to the shopper through a smart speaker or voice interface.\n\n"
        "Core Voice Instructions:\n"
        "1. Keep all responses brief, natural, and conversational—under 2 to 3 spoken sentences per turn.\n"
        "2. Avoid complex lists, raw URLs, and markdown formatting (no asterisks, hash headers, or bullet symbols).\n"
        "3. Always explicitly verify items, quantities, and prices before asking for checkout confirmation.\n"
        "4. When quoting promotions, mention the code and dollar or percentage savings directly.\n"
        "5. If an item is added or updated, clearly confirm the total number of items now in the cart.\n"
        "6. Provide crisp, clear guidance when looking up order status or return policies."
    )


# ---------------------------------------------------------------------------
# MCP Apps UI Resource Registration (@modelcontextprotocol/ext-apps)
# ---------------------------------------------------------------------------
register_mcp_apps_resources(mcp)

# ---------------------------------------------------------------------------
# Streamable HTTP MCP Application Creation
# Configured with stateless_http=True and single-endpoint routing at POST /mcp
# ---------------------------------------------------------------------------
mcp_sub_app = mcp.http_app(
    path="/mcp",
    stateless_http=True,
    transport="streamable-http",
)

# ---------------------------------------------------------------------------
# Production Header Validation & Wire Protocol Middleware
# ---------------------------------------------------------------------------
class MCPWireProtocolMiddleware(BaseHTTPMiddleware):
    """
    Strictly enforces the 2025-11-25 MCP Streamable HTTP Specification:
    1. Protocol version verification: MCP-Protocol-Version: 2025-11-25.
    2. Origin gating: HTTP 403 Forbidden for untrusted origins (CORS security).
    3. JSON-RPC header mirroring & validation: Mcp-Method and Mcp-Name checks.
    4. CORS preflight OPTIONS handling.
    """

    def __init__(self, app, allowed_origins: Optional[List[str]] = None):
        super().__init__(app)
        self.allowed_origins = allowed_origins if allowed_origins is not None else ["*"]

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        method = request.method
        path = request.url.path

        # 1. Origin header security check (returns HTTP 403 Forbidden for untrusted origins)
        if origin:
            if "*" not in self.allowed_origins and origin not in self.allowed_origins:
                logger.warning(f"Rejected untrusted Origin: {origin!r}")
                return JSONResponse(
                    {
                        "error": "Forbidden: Untrusted Origin",
                        "message": f"Origin {origin!r} is not allowed to access this MCP server.",
                    },
                    status_code=403,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                    },
                )

        # 2. CORS Preflight OPTIONS handling
        if method == "OPTIONS":
            allow_origin = origin if origin else ("*" if "*" in self.allowed_origins else "")
            headers = {
                "Access-Control-Allow-Origin": allow_origin,
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS, DELETE",
                "Access-Control-Allow-Headers": (
                    "Content-Type, MCP-Protocol-Version, Mcp-Method, Mcp-Name, "
                    "Mcp-Session-Id, Authorization, Accept"
                ),
                "Access-Control-Expose-Headers": (
                    "MCP-Protocol-Version, Mcp-Method, Mcp-Name, Mcp-Session-Id"
                ),
                "Access-Control-Max-Age": "86400",
            }
            return Response(status_code=204, headers=headers)

        # 3. Health & Readiness check endpoint (for AWS Lambda Web Adapter readiness check)
        if path == "/health" and method == "GET":
            return JSONResponse(
                {
                    "status": "healthy",
                    "server": "EchoCart-Nexus-MCP",
                    "mcp_protocol_version": REQUIRED_MCP_PROTOCOL_VERSION,
                    "stateless_http": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                status_code=200,
            )

        # 4. Strict Protocol Checks for /mcp endpoint
        if path == "/mcp" and method == "POST":
            # Protocol Version Check
            proto_header = request.headers.get("mcp-protocol-version")
            if proto_header != REQUIRED_MCP_PROTOCOL_VERSION:
                logger.warning(f"Invalid or missing MCP-Protocol-Version: {proto_header!r}")
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32600,
                            "message": (
                                f"Invalid or missing MCP-Protocol-Version header. "
                                f"Expected '{REQUIRED_MCP_PROTOCOL_VERSION}', got {proto_header!r}"
                            ),
                        },
                    },
                    status_code=400,
                    headers={
                        "MCP-Protocol-Version": REQUIRED_MCP_PROTOCOL_VERSION,
                    },
                )

            # Inspect and buffer JSON-RPC payload
            body = await request.body()
            try:
                payload = json.loads(body) if body else {}
            except Exception as e:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32700,
                            "message": f"Parse error: {str(e)}",
                        },
                    },
                    status_code=400,
                    headers={
                        "MCP-Protocol-Version": REQUIRED_MCP_PROTOCOL_VERSION,
                    },
                )

            body_method = payload.get("method")
            body_params = payload.get("params") or {}
            body_name = body_params.get("name") or body_params.get("uri")

            req_method_header = request.headers.get("mcp-method")
            req_name_header = request.headers.get("mcp-name")

            # Validate Mcp-Method header if provided
            if req_method_header and body_method and req_method_header != body_method:
                logger.warning(f"Mcp-Method mismatch: header={req_method_header!r} vs body={body_method!r}")
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32600,
                            "message": (
                                f"Mcp-Method header mismatch: Header '{req_method_header}' "
                                f"does not match payload method '{body_method}'"
                            ),
                        },
                    },
                    status_code=400,
                    headers={
                        "MCP-Protocol-Version": REQUIRED_MCP_PROTOCOL_VERSION,
                    },
                )

            # Validate Mcp-Name header if provided
            if req_name_header and body_name and req_name_header != str(body_name):
                logger.warning(f"Mcp-Name mismatch: header={req_name_header!r} vs body={body_name!r}")
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32600,
                            "message": (
                                f"Mcp-Name header mismatch: Header '{req_name_header}' "
                                f"does not match target name '{body_name}'"
                            ),
                        },
                    },
                    status_code=400,
                    headers={
                        "MCP-Protocol-Version": REQUIRED_MCP_PROTOCOL_VERSION,
                    },
                )

            # Execute request through FastMCP downstream handler
            response = await call_next(request)

            # Mirror wire headers in HTTP response
            response.headers["MCP-Protocol-Version"] = REQUIRED_MCP_PROTOCOL_VERSION
            if body_method:
                response.headers["Mcp-Method"] = body_method
            elif req_method_header:
                response.headers["Mcp-Method"] = req_method_header

            if body_name:
                response.headers["Mcp-Name"] = str(body_name)
            elif req_name_header:
                response.headers["Mcp-Name"] = req_name_header

            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin

            # Content-Security-Policy header for UI resources
            if body_name and ("ui://" in str(body_name) or "cart-view" in str(body_name) or "product-carousel" in str(body_name)):
                response.headers["Content-Security-Policy"] = CSP_HEADER_VALUE

            response.headers["Access-Control-Expose-Headers"] = (
                "MCP-Protocol-Version, Mcp-Method, Mcp-Name, Mcp-Session-Id, Content-Security-Policy"
            )
            return response

        # Non-/mcp requests pass-through
        response = await call_next(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        return response


# ---------------------------------------------------------------------------
# Construct Parent Application with Preserved Lifespan & MCP Apps Mounted
# ---------------------------------------------------------------------------
app = Starlette(lifespan=mcp_sub_app.lifespan)
app.add_middleware(MCPWireProtocolMiddleware, allowed_origins=ALLOWED_ORIGINS)
mount_mcp_apps_http(app)
app.mount("", mcp_sub_app)

# ---------------------------------------------------------------------------
# Entrypoint for Local Testing / Direct Invocation
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info(f"Starting EchoCart Nexus MCP Server on {host}:{port}")
    uvicorn.run("main:app", host=host, port=port, log_level="info")
