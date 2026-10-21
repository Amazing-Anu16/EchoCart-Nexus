# EchoCart Nexus 🛒✨
### Voice-First Intelligent Commerce with Streamable HTTP MCP & Alexa+ Multimodal Display

> **Amazon Developer Hackathon Submission**  
> *Equipping AI shopping agents with Model Context Protocol (MCP) Streamable HTTP transport and interactive MCP App cards for simulated Alexa+ smart displays.*

[![Protocol](https://img.shields.io/badge/MCP--Protocol--Version-2025--11--25-00CAFF?style=flat-square)](https://modelcontextprotocol.io/)
[![FastMCP](https://img.shields.io/badge/FastMCP-v4.1.2-blue?style=flat-square)](https://github.com/jlowin/fastmcp)
[![Next.js](https://img.shields.io/badge/Next.js-16.4-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square)](LICENSE)

---

## 1. System Architecture Overview

EchoCart Nexus is an end-to-end multimodal commerce architecture uniting voice-first natural language processing, streamable serverless tool execution, and sandboxed interactive UI cards.

### Architectural Component Diagram

```
+-----------------------------------------------------------------------------------------+
|                                CLIENT TIER (Echo Show Display)                          |
|                                                                                         |
|  +-------------------------------------+   +-----------------------------------------+  |
|  |     Conversational Agent Stream     |   |          AppBridgeIframe Host           |  |
|  |    (Voice Mic, TTS, ChatBox)        |   |   (Sandboxed <iframe>: allow-scripts)   |  |
|  +-------------------------------------+   +-----------------------------------------+  |
|                    ^                                            ^                       |
|                    |                                            |                       |
|                    v                                            v                       |
|  +-----------------------------------------------------------------------------------+  |
|  |                     EchoCart Agent Orchestration Engine                           |  |
|  |         Intent Parsing | Tool Calling Dispatcher | Progressive Enhancement        |  |
|  +-----------------------------------------------------------------------------------+  |
|                                            ^                                            |
|                                            | (Streamable HTTP JSON-RPC 2.0)             |
|                                            v                                            |
|  +-----------------------------------------------------------------------------------+  |
|  |                      EchoCart Streamable HTTP MCP Client                          |  |
|  |   MCP-Protocol-Version: 2025-11-25 | Mcp-Method / Mcp-Name Header Mirroring       |  |
|  +-----------------------------------------------------------------------------------+  |
+--------------------------------------------|--------------------------------------------+
                                             |
                   HTTP POST /mcp            |  HTTP GET /mcp-apps/*
                   (JSON-RPC 2.0 / SSE)      |  (text/html;profile=mcp-app)
                                             v
+-----------------------------------------------------------------------------------------+
|                               SERVER TIER (AWS Lambda / Docker)                         |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |               MCPWireProtocolMiddleware (CORS, 403 Origin Gate, Version)          |  |
|  +-----------------------------------------------------------------------------------+  |
|                    |                                            |                       |
|                    v                                            v                       |
|  +-------------------------------------+   +-----------------------------------------+  |
|  |       FastMCP Core Tools & State    |   |           MCP Apps Extension            |  |
|  |  * search_catalog (_meta.ui bound)  |   |  * ui://echocart/cart-view.html         |  |
|  |  * manage_cart (_meta.ui bound)     |   |  * ui://echocart/product-carousel.html  |  |
|  |  * get_order_status                 |   |  * CSP: default-src 'none'; ...         |  |
|  +-------------------------------------+   +-----------------------------------------+  |
|                    |                                            |                       |
|                    v                                            v                       |
|  +-----------------------------------------------------------------------------------+  |
|  |        AWS Lambda Web Adapter (Response Streaming / Public Function URL)          |  |
|  +-----------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Core Protocol Implementations

### A. Streamable HTTP MCP Specification (`2025-11-25`)
- **Stateless HTTP Transport**: All RPC commands dispatch to unified endpoint `POST /mcp`.
- **Wire Header Mirroring**: Server requires and mirrors:
  - `MCP-Protocol-Version: 2025-11-25`
  - `Mcp-Method: <method_name>`
  - `Mcp-Name: <tool_or_resource_name>`
- **Security & Origin Gating**: Validates browser `Origin` headers, returning `403 Forbidden` for untrusted origins.
- **Serverless Response Streaming**: Packaged with AWS Lambda Web Adapter (`AWS_LWA_INVOKE_MODE=response_stream`) streaming chunks through Lambda Function URLs.

### B. MCP Apps Extension (`@modelcontextprotocol/ext-apps`)
- **Tool UI Binding**: Tools advertise rich UI template pointers in `_meta.ui.resourceUri`:
  - `manage_cart` ➔ `ui://echocart/cart-view.html`
  - `search_catalog` ➔ `ui://echocart/product-carousel.html`
- **MIME & CSP Compliance**: UI templates served with MIME type `text/html;profile=mcp-app` and strict Content Security Policy (`default-src 'none'; script-src 'unsafe-inline'; ...`).
- **Bidirectional PostMessage Bridge**:
  - `ui/initialize`: Handshake establishing guest app capabilities.
  - `ui/tool-result`: Host delivers real-time cart and catalog state to the iframe.
  - `tools/call`: Tapping buttons inside the sandboxed iframe emits JSON-RPC `tools/call` for `manage_cart` back to the host, triggering live backend execution.
- **Progressive Enhancement**: All tool results return dual content:
  - `content[0]`: Structured JSON machine payload.
  - `content[1]`: Natural-language voice summary for screenless smart speakers.

---

## 3. Quick Start (Single-Command Run)

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- Alternatively: Python 3.12+ and Node.js 20+

### Option 1: Docker Compose (Recommended)
Spin up both the FastMCP backend and the Next.js simulated Echo Show frontend with one command:

```bash
docker compose up --build
```

- **Frontend (Simulated Alexa+ Display)**: [http://localhost:3000](http://localhost:3000)
- **Backend (Streamable HTTP MCP Server)**: [http://localhost:8080](http://localhost:8080)
- **Readiness Check**: [http://localhost:8080/health](http://localhost:8080/health)
- **Direct Template Preview**: [http://localhost:8080/mcp-apps](http://localhost:8080/mcp-apps)

---

### Option 2: Running Locally Without Docker

#### 1. Backend Server
```bash
# In repository root
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8080
```

#### 2. Frontend Application
```bash
cd frontend
npm install
npm run dev -- -p 3000
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 4. End-to-End Automated Testing

### Run Backend Pytest Suite (29 Tests)
```bash
python -m pytest backend/ -v
```

### Run Automated E2E Curl Verification Script
```bash
# Linux / macOS / Git Bash / WSL
chmod +x test_e2e.sh
./test_e2e.sh

# Windows PowerShell
.\test_e2e.ps1
```

The script automatically tests:
1. Health & readiness endpoints.
2. Missing and invalid `MCP-Protocol-Version` rejection.
3. Handshake (`initialize`) and tool discovery (`tools/list`).
4. Companion UI resource pointers in `_meta.ui.resourceUri`.
5. Direct HTTP template rendering with Content-Security-Policy headers.
6. Progressive enhancement textual voice summaries.

---

## 5. Serverless Cloud Deployment (AWS Lambda)

The backend is containerized for serverless deployment on **AWS Lambda** via **AWS Lambda Web Adapter**:

### AWS SAM Deployment
```bash
cd infra/sam
sam build
sam deploy --guided
```

### Terraform Deployment
```bash
cd infra/terraform
terraform init
terraform apply -var="image_uri=<YOUR_ECR_REPO_URI>:latest"
```

The template automatically creates a public **AWS Lambda Function URL** with response streaming (`InvokeMode: RESPONSE_STREAM`) and pre-configured CORS headers.

---

## 6. Hackathon Collaborator Access Instructions

If this repository is kept private during development, hackathon organizers and judges must be added as collaborators.

### Step-by-Step Collaborator Setup
1. Navigate to the GitHub repository page: `https://github.com/Amazing-Anu16/EchoCart-Nexus`.
2. Click on **Settings** (tab along the top).
3. In the left sidebar under *Access*, select **Collaborators**.
4. Click the green **Add people** button.
5. Add each of the following official hackathon review accounts:
   - `testing@devpost.com`
   - `knmeiss`
   - `giolaq`
   - `anishamalde`
   - `mosesroth`
   - `emersonsklar`
6. Click **Add to this repository**.

> [!IMPORTANT]
> **7-Day GitHub Invitation Expiration Notice:**  
> GitHub collaborator invitations automatically expire **7 days** after being sent.  
> If an invitation lapses before review:
> 1. Return to **Settings ➔ Collaborators**.
> 2. Locate any invitations marked as *Pending Invite / Expired*.
> 3. Click the **Cancel** button next to the lapsed user, and immediately re-send by clicking **Add people** and re-entering their username.

---

## 7. Video Demonstration Script

Use this 3-minute video presentation script for hackathon recording:

| Time | Scene | Script & Action Points |
| :--- | :--- | :--- |
| **0:00 - 0:30** | **Introduction** | *"Welcome to EchoCart Nexus, a next-generation voice-first intelligent shopping agent built for the Amazon Developer Hackathon. Today, smart displays like the Echo Show require more than plain text speech—they need interactive, sandboxed visual experiences orchestrated directly by the AI model. We built EchoCart Nexus using the 2025-11-25 Streamable HTTP Model Context Protocol and the official MCP Apps extension."* |
| **0:30 - 1:00** | **Architecture & Launch** | Show terminal running `docker compose up`. Show the split-screen Echo Show 1080p ambient layout. *"With a single command, Docker spins up our FastMCP Python server and our Next.js frontend. The client performs an MCP handshake, automatically discovering tools, resources, and companion UI metadata."* |
| **1:00 - 1:45** | **Voice Search & Carousel Card** | Click or speak: *"Alexa, search for noise cancelling headphones"*. Point to the Left Transcript showing the tool call `search_catalog` and latency badge. Point to the Right Visual Stage displaying `product-carousel.html`. *"Notice the server didn't just return products—it returned `_meta.ui.resourceUri = ui://echocart/product-carousel.html`. Our AppBridge host rendered the interactive horizontal product slider inside a secure sandboxed iframe with strict Content Security Policy."* |
| **1:45 - 2:30** | **Bidirectional PostMessage Bridge** | Click **Add to Cart** on the headphones card, then switch to the **Shopping Cart View**. Tap the stepper `+` button inside the iframe. Open the **Wire Inspector**. *"Notice what just happened: when I tapped '+' inside the sandboxed iframe, it didn't do a full page reload. It emitted a JSON-RPC `tools/call` for `manage_cart` over `window.postMessage`. Our host intercepted it, executed it on our server, and pushed the updated totals back into the view."* |
| **2:30 - 3:00** | **Progressive Enhancement & Cloud** | Toggle voice speech audio to hear Alexa confirm the order total. Show `infra/sam/template.yaml` for AWS Lambda Web Adapter. *"For screenless devices, EchoCart Nexus provides progressive enhancement with companion voice speech. In the cloud, it deploys serverlessly to AWS Lambda with streaming Function URLs. Thank you for watching!"* |

---

## 8. License

Distributed under the [MIT License](LICENSE).
