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

## 3. Local Execution & Testing

### Running the Test Suite
```bash
python -m pytest backend/test_server.py -v
```

### Starting the Server Locally
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

---

## 4. Curl & Wire Verification Recipes

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

## 5. Docker & AWS Lambda Deployment

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
