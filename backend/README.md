# EchoCart Nexus MCP Server

Production-grade, self-hosted **Model Context Protocol (MCP)** server adhering to the **2025-11-25 Streamable HTTP Specification**, containerized and optimized for serverless execution on **AWS Lambda** via the **AWS Lambda Web Adapter**.

---

## 1. Architectural Highlights

- **Specification Conformance**: Strictly enforces `MCP-Protocol-Version: 2025-11-25` and JSON-RPC 2.0 framing.
- **Transport Mechanism**: Streamable HTTP with `stateless_http=True` over a unified endpoint: `POST /mcp`.
- **Header Validation & Mirroring**:
  - Validates `Mcp-Method` against incoming JSON-RPC `method`.
  - Validates `Mcp-Name` against incoming `params.name` or `params.uri`.
  - Mirrors `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` in HTTP response headers.
- **Origin Gating & CORS**: Enforces browser `Origin` verification, returning `403 Forbidden` for untrusted origins, with preflight `OPTIONS` support.
- **AWS Lambda Web Adapter**: Leverages `public.ecr.aws/awsguru/aws-lambda-adapter` over a slim `python:3.12-slim` base container, streaming responses via `AWS_LWA_INVOKE_MODE=response_stream` on port `8080`.

---

## 2. Core MCP Primitives

### Tools
| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `search_catalog` | `query: str`, `category: str = None` | Search catalog items returning SKU, title, price, stock, ratings. |
| `manage_cart` | `action: str`, `sku: str`, `quantity: int`, `user_token: str` | Manages cart state (`add`, `update`, `remove`) with structured cart totals. |
| `get_order_status` | `order_id: str`, `user_token: str` | Retrieves delivery status, carrier, tracking number, and status timeline. |

### Resources
| Resource URI | MIME Type | Description |
| :--- | :--- | :--- |
| `resource://store/promotions/current` | `application/json` | Active discount coupons (`NEXUS20`, `VOICEFIRST`, `FREESHIP`). |
| `resource://store/policies/returns` | `text/plain` | 30-day returns and warranty policy guidelines. |

### Prompts
| Prompt Name | Role | Description |
| :--- | :--- | :--- |
| `checkout_assistant` | System Prompt | Conversational system prompt for concise, voice-first commerce checkout. |

---

## 3. MCP Apps Extension (`@modelcontextprotocol/ext-apps`)

EchoCart Nexus implements the **MCP Apps Extension** specification, equipping MCP tools with interactive UI cards rendered inside sandboxed `<iframe>` elements for simulated **Alexa+ Smart Displays** (e.g. Echo Show 10/15).

### UI Metadata Binding
Tools declare a pointer to their companion UI templates in their metadata:
- **`manage_cart`** ➔ `_meta.ui.resourceUri`: `ui://echocart/cart-view.html`
- **`search_catalog`** ➔ `_meta.ui.resourceUri`: `ui://echocart/product-carousel.html`

Both `tools/list` and `tools/call` responses bundle `_meta.ui.resourceUri` so UI-enabled clients can automatically mount the sandboxed views.

### UI Templates & Sandboxed Resources
Templates are served as MCP resources with:
- **URI Scheme**: `ui://echocart/<template-name>.html`
- **MIME Type**: `text/html;profile=mcp-app`
- **Content Security Policy (CSP)**: Declared in `_meta.ui.csp` and enforced via `<meta http-equiv="Content-Security-Policy">` and HTTP headers:
  ```text
  default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'none'; frame-ancestors *;
  ```

| Template | File | Endpoint | Features |
| :--- | :--- | :--- | :--- |
| **Cart Summary Card** | `backend/templates/cart-view.html` | `/mcp-apps/cart-view.html` | Responsive touch-friendly cart summary, vector thumbnails, itemized subtotal/tax/shipping, and touch stepper buttons (`+` / `-`). |
| **Product Carousel** | `backend/templates/product-carousel.html` | `/mcp-apps/product-carousel.html` | Horizontal touch slider with scroll-snapping, category filters, ratings, badges, and "Add to Cart" button. |
| **Alexa+ Display Simulator** | `backend/templates/alexa-simulator.html` | `/mcp-apps` or `/mcp-apps/alexa-simulator.html` | Hardware bezel simulator (Echo Show) hosting sandboxed iframes with live PostMessage event logger. |

### Bidirectional PostMessage Bridge
Communication between the guest UI iframe and the host client conforms strictly to JSON-RPC 2.0 over `window.postMessage`:
1. **Handshake**: The guest view emits `ui/initialize` on mount:
   ```json
   {
     "jsonrpc": "2.0",
     "id": "init-1",
     "method": "ui/initialize",
     "params": {
       "appInfo": { "name": "EchoCart-Cart-View", "version": "1.0.0" },
       "appCapabilities": { "tools": { "call": true } },
       "protocolVersion": "2025-11-25"
     }
   }
   ```
2. **State Reception**: The host sends initial data or updates using `ui/tool-result`:
   ```json
   {
     "jsonrpc": "2.0",
     "method": "ui/tool-result",
     "params": { "cart": { "items": [...], "total_items": 2, "total_price": 379.98 } }
   }
   ```
3. **Tool Invocation**: Tapping stepper buttons (`+` / `-`) or "Add to Cart" emits `tools/call` back to the host:
   ```json
   {
     "jsonrpc": "2.0",
     "id": "call-1",
     "method": "tools/call",
     "params": {
       "name": "manage_cart",
       "arguments": { "action": "update", "sku": "ECHO-PRO-01", "quantity": 2, "user_token": "usr_token_alpha" }
     }
   }
   ```

### Progressive Enhancement
For screenless or headless interactions (e.g. smart speakers without screens or voice-only mode), all MCP tool execution results include companion natural-language voice summaries in `content[1]`. Headless clients read the textual speech response, while screen-enabled clients render the interactive MCP App.


---

## 4. Local Execution & Testing

### Running the Complete Test Suite
```bash
# Run both wire protocol and MCP Apps extension test suites
python -m pytest backend/ -v

# Run MCP Apps extension tests specifically
python -m pytest backend/test_mcp_apps.py -v
```

### Starting the Server Locally
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

### Opening the Simulated Alexa+ Display
Navigate to `http://localhost:8080/mcp-apps` to view the interactive Echo Show simulator running the sandboxed MCP Apps iframe.

---

## 5. Curl & Wire Verification Recipes

### 1. Protocol Ping
```bash
curl -i -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Mcp-Method: ping" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "ping"}'
```

### 2. Search Product Catalog
```bash
curl -i -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Mcp-Method: tools/call" \
  -H "Mcp-Name: search_catalog" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_catalog",
      "arguments": {"query": "headphones", "category": "audio"}
    }
  }'
```

### 3. Add Item to Cart
```bash
curl -i -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Mcp-Method: tools/call" \
  -H "Mcp-Name: manage_cart" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "manage_cart",
      "arguments": {
        "action": "add",
        "sku": "ECHO-PRO-01",
        "quantity": 1,
        "user_token": "usr_mobile_session_99"
      }
    }
  }'
```

### 4. Fetch Order Status
```bash
curl -i -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Mcp-Method: tools/call" \
  -H "Mcp-Name: get_order_status" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "get_order_status",
      "arguments": {
        "order_id": "ORD-98241",
        "user_token": "usr_token_alpha"
      }
    }
  }'
```

### 5. Read Store Promotions Resource
```bash
curl -i -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Mcp-Method: resources/read" \
  -H "Mcp-Name: resource://store/promotions/current" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "resources/read",
    "params": {
      "uri": "resource://store/promotions/current"
    }
  }'
```

### 6. Read Return Policies Resource
```bash
curl -i -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Mcp-Method: resources/read" \
  -H "Mcp-Name: resource://store/policies/returns" \
  -d '{
    "jsonrpc": "2.0",
    "id": 6,
    "method": "resources/read",
    "params": {
      "uri": "resource://store/policies/returns"
    }
  }'
```

### 7. Get Checkout Voice Assistant Prompt
```bash
curl -i -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Mcp-Method: prompts/get" \
  -H "Mcp-Name: checkout_assistant" \
  -d '{
    "jsonrpc": "2.0",
    "id": 7,
    "method": "prompts/get",
    "params": {
      "name": "checkout_assistant"
    }
  }'
```

---

## 6. Docker & AWS Lambda Deployment

### Build Container Image
```bash
docker build -t echocart-mcp-server backend/
```

### Test Container Locally
```bash
docker run -p 8080:8080 -e ALLOWED_ORIGINS="*" echocart-mcp-server
```

### Deploy to AWS Lambda
1. Tag and push container to Amazon ECR.
2. Create Lambda function with **Container Image** package type.
3. In Lambda Configuration:
   - **Invoke Mode**: Set Function URL invoke mode to `RESPONSE_STREAM` or configure AWS Lambda Web Adapter `AWS_LWA_INVOKE_MODE=response_stream`.
   - **Timeout**: Set to 30-60 seconds.
   - **Memory**: 512 MB - 1024 MB.
