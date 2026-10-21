# EchoCart Nexus - Alexa+ Multimodal Smart Display (Next.js)

Production-grade simulated **Amazon Echo Show (Alexa+)** multimodal web application built with **Next.js (App Router, Tailwind CSS, TypeScript)** acting as the intelligent agent host that orchestrates the user, voice/text prompts, the LLM, and the **Streamable HTTP MCP Server** with the **MCP Apps Extension (`@modelcontextprotocol/ext-apps`)**.

---

## 1. Architectural Highlights

- **Visual Design & Shell (`EchoShowCard.tsx`)**:
  - Emulates an **Amazon Echo Show** 1080p ambient layout.
  - Subtle dark slate chassis (`#05080E`), ambient glow reflections, and animated cyan voice listening indicator strip.
  - Live digital clock, date, weather widget (72°F Partly Cloudy), and Wi-Fi 6 status.
  - Split-screen layout:
    - **Left (40%)**: Conversational Voice Transcript Stream (`ChatBox.tsx`).
    - **Right (60%)**: Multimodal Interactive Visual Stage (`AppBridgeIframe.tsx`).

- **MCP Client Integration (`mcpClient.ts`)**:
  - Implements JSON-RPC 2.0 communication over Streamable HTTP adhering to `MCP-Protocol-Version: 2025-11-25`.
  - Header validation & mirroring (`Mcp-Method`, `Mcp-Name`).
  - Automatic handshake (`initialize` / `notifications/initialized`) and discovery of tools (`tools/list`), resources (`resources/list`), and prompts (`prompts/list`).
  - Handles both `text/event-stream` (SSE) and `application/json` responses.

- **Agent Orchestration Engine (`agentEngine.ts`)**:
  - Parses voice/text intent for shopping, cart operations, order tracking, and store policies.
  - Routes tool calls to the MCP server with proper parameters and wire headers.
  - Detects `_meta.ui.resourceUri` in tool outputs and surfaces companion UI templates.
  - Progressive enhancement: Synthesizes concise natural language voice responses for screenless devices while driving the visual card.

- **MCP App Host Container (`AppBridgeIframe.tsx`)**:
  - Detects `_meta.ui.resourceUri` (e.g. `ui://echocart/cart-view.html` or `ui://echocart/product-carousel.html`).
  - Renders view templates in a secure, sandboxed iframe (`sandbox="allow-scripts allow-forms allow-same-origin"`).
  - Maintains a bidirectional `window.postMessage` bridge:
    - Answers guest `ui/initialize` with host metadata.
    - Pushes state via `ui/tool-result`.
    - Intercepts guest `tools/call` requests (e.g., when the user taps steppers `+` / `−` or "Add to Cart"), executes them against the MCP backend, and returns execution results to the view.
  - Integrated Wire Protocol Inspector to monitor real-time JSON-RPC frame exchanges.

---

## 2. Directory Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css         # Tailwind CSS & ambient tokens
│   │   ├── layout.tsx          # Root layout & Alexa+ metadata
│   │   └── page.tsx            # Main page mounting EchoShowCard
│   ├── components/
│   │   ├── AppBridgeIframe.tsx # Sandboxed iframe host & postMessage bridge
│   │   ├── ChatBox.tsx         # Transcript, voice mic, speech synthesis
│   │   └── EchoShowCard.tsx    # Echo Show 1080p ambient chassis & split view
│   └── lib/
│       ├── agentEngine.ts      # Voice intent router & tool orchestration
│       └── mcpClient.ts        # Streamable HTTP MCP Client (2025-11-25)
├── package.json
└── tsconfig.json
```

---

## 3. Getting Started

### 1. Start the MCP Backend Server (Port 8080)
From the repository root:
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8080
```

### 2. Start the Frontend Application (Port 3000)
From `/frontend`:
```bash
npm run dev -- -p 3000
```

### 3. Open in Browser
Open `http://localhost:3000` to interact with the simulated Echo Show display.
