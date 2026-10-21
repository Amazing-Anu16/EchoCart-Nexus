"""
EchoCart Nexus - MCP Apps Extension (@modelcontextprotocol/ext-apps)
Helper modules for mounting interactive sandboxed UI cards (MCP Apps)
for Alexa+ smart displays, managing UI metadata binding, CSP policies,
and HTTP/JSON-RPC template serving.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import mcp.types as types
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

logger = logging.getLogger("echocart_mcp.apps")

# ---------------------------------------------------------------------------
# Protocol Constants
# ---------------------------------------------------------------------------
MCP_APP_PROFILE = "mcp-app"
MCP_APP_MIME_TYPE = "text/html;profile=mcp-app"

CART_VIEW_URI = "ui://echocart/cart-view.html"
PRODUCT_CAROUSEL_URI = "ui://echocart/product-carousel.html"

# Content Security Policy (CSP) Configuration conforming to ext-apps standard
DEFAULT_APP_CSP_METADATA = {
    "connectDomains": [],
    "resourceDomains": [
        "https://fonts.googleapis.com",
        "https://fonts.gstatic.com",
    ],
    "frameDomains": [],
    "baseUriDomains": [],
}

CSP_HEADER_VALUE = (
    "default-src 'none'; "
    "script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https:; "
    "connect-src 'none'; "
    "frame-ancestors *;"
)

# ---------------------------------------------------------------------------
# Template Discovery & Loading
# ---------------------------------------------------------------------------
def get_templates_dir() -> Path:
    """Resolve backend/templates directory."""
    return Path(__file__).resolve().parent / "templates"


def load_template(template_name: str) -> str:
    """Load an HTML template by filename from the templates directory."""
    templates_dir = get_templates_dir()
    template_path = templates_dir / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"MCP App template not found at {template_path}")
    return template_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tool Result & Metadata Helpers
# ---------------------------------------------------------------------------
def build_ui_metadata(resource_uri: str, csp: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Constructs the _meta.ui block conforming to @modelcontextprotocol/ext-apps spec.
    """
    ui_meta: Dict[str, Any] = {
        "resourceUri": resource_uri,
    }
    if csp is not None:
        ui_meta["csp"] = csp
    return {"ui": ui_meta}


def create_call_tool_result(
    structured_data: Any,
    resource_uri: str,
    text_summary: Optional[str] = None,
    is_error: bool = False,
) -> types.CallToolResult:
    """
    Wraps tool return values in an MCP CallToolResult with:
    1. content[0]: JSON-serialized structured data (for tool-call parsers).
    2. content[1]: Natural language text summary for screenless/headless voice agents (Progressive Enhancement).
    3. _meta.ui.resourceUri: Pointer for UI-capable clients to render the sandboxed iframe.
    """
    content: List[types.TextContent] = [
        types.TextContent(
            type="text",
            text=json.dumps(structured_data, indent=2) if not isinstance(structured_data, str) else structured_data,
        )
    ]

    if text_summary:
        content.append(types.TextContent(type="text", text=text_summary))

    meta = build_ui_metadata(resource_uri)

    return types.CallToolResult(
        content=content,
        meta=meta,
        is_error=is_error,
    )


# ---------------------------------------------------------------------------
# MCP Server Resource Registration
# ---------------------------------------------------------------------------
def register_mcp_apps_resources(mcp_server: FastMCP) -> None:
    """
    Registers the UI templates as MCP resources with:
    - URI scheme ui://echocart/...
    - MIME type text/html;profile=mcp-app
    - _meta.ui.csp headers/metadata
    """
    logger.info("Registering MCP Apps UI resources on FastMCP server...")

    @mcp_server.resource(
        uri=CART_VIEW_URI,
        name="cart_view_template",
        description="Interactive touch-friendly cart summary card template for Alexa+ display.",
        mime_type=MCP_APP_MIME_TYPE,
        meta={"ui": {"csp": DEFAULT_APP_CSP_METADATA}},
    )
    def get_cart_view_template() -> str:
        """Returns the sandboxed HTML/JS view for cart management."""
        return load_template("cart-view.html")

    @mcp_server.resource(
        uri=PRODUCT_CAROUSEL_URI,
        name="product_carousel_template",
        description="Interactive horizontal product slider template for Alexa+ display.",
        mime_type=MCP_APP_MIME_TYPE,
        meta={"ui": {"csp": DEFAULT_APP_CSP_METADATA}},
    )
    def get_product_carousel_template() -> str:
        """Returns the sandboxed HTML/JS view for catalog exploration."""
        return load_template("product-carousel.html")


# ---------------------------------------------------------------------------
# Starlette HTTP Mounting for Iframe Previews & Direct Ingestion
# ---------------------------------------------------------------------------
def mount_mcp_apps_http(starlette_app: Starlette) -> None:
    """
    Exposes HTTP GET endpoints under /mcp-apps/ to serve UI views
    directly into simulated Alexa+ iframes with strict CSP and MIME headers.
    """

    async def serve_cart_view(request: Request) -> Response:
        html_content = load_template("cart-view.html")
        return Response(
            content=html_content,
            media_type=MCP_APP_MIME_TYPE,
            headers={
                "Content-Type": f"{MCP_APP_MIME_TYPE}; charset=utf-8",
                "Content-Security-Policy": CSP_HEADER_VALUE,
                "X-Frame-Options": "ALLOWALL",
                "X-Content-Type-Options": "nosniff",
                "Access-Control-Allow-Origin": "*",
            },
        )

    async def serve_product_carousel(request: Request) -> Response:
        html_content = load_template("product-carousel.html")
        return Response(
            content=html_content,
            media_type=MCP_APP_MIME_TYPE,
            headers={
                "Content-Type": f"{MCP_APP_MIME_TYPE}; charset=utf-8",
                "Content-Security-Policy": CSP_HEADER_VALUE,
                "X-Frame-Options": "ALLOWALL",
                "X-Content-Type-Options": "nosniff",
                "Access-Control-Allow-Origin": "*",
            },
        )

    async def serve_dynamic_template(request: Request) -> Response:
        template_name = request.path_params.get("template_name", "")
        if not template_name.endswith(".html"):
            template_name += ".html"
        try:
            html_content = load_template(template_name)
            return Response(
                content=html_content,
                media_type=MCP_APP_MIME_TYPE,
                headers={
                    "Content-Type": f"{MCP_APP_MIME_TYPE}; charset=utf-8",
                    "Content-Security-Policy": CSP_HEADER_VALUE,
                    "X-Frame-Options": "ALLOWALL",
                    "X-Content-Type-Options": "nosniff",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except FileNotFoundError:
            return Response(
                content=json.dumps({"error": f"Template '{template_name}' not found."}),
                status_code=404,
                media_type="application/json",
            )

    async def serve_simulator(request: Request) -> Response:
        html_content = load_template("alexa-simulator.html")
        return HTMLResponse(
            content=html_content,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Access-Control-Allow-Origin": "*",
            },
        )

    starlette_app.add_route("/mcp-apps", serve_simulator, methods=["GET"])
    starlette_app.add_route("/mcp-apps/", serve_simulator, methods=["GET"])
    starlette_app.add_route("/mcp-apps/alexa-simulator.html", serve_simulator, methods=["GET"])
    starlette_app.add_route("/mcp-apps/cart-view.html", serve_cart_view, methods=["GET"])
    starlette_app.add_route("/mcp-apps/product-carousel.html", serve_product_carousel, methods=["GET"])
    starlette_app.add_route("/mcp-apps/{template_name}", serve_dynamic_template, methods=["GET"])
    logger.info("Mounted /mcp-apps/* HTTP routes for sandboxed UI views and simulator.")

