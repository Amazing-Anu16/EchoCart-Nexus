/**
 * EchoCart Nexus - Agent Orchestration Engine
 * Orchestrates user voice/text inputs, executes MCP tools over Streamable HTTP,
 * extracts MCP Apps UI metadata (_meta.ui.resourceUri), and synthesizes natural language
 * voice-first responses for simulated Alexa+ smart displays.
 */

import { EchoCartMCPClient, MCPCallToolResult, defaultMcpClient } from "./mcpClient";

export interface AgentExecutionStep {
  id: string;
  timestamp: string;
  userPrompt: string;
  intent: string;
  toolCall?: {
    name: string;
    args: Record<string, any>;
    latencyMs: number;
  };
  toolResult?: MCPCallToolResult;
  rawPayload?: any;
  uiResourceUri?: string;
  assistantResponse: string;
}

export class EchoCartAgentEngine {
  private client: EchoCartMCPClient;
  private currentUserToken: string = "usr_token_alpha";

  constructor(client: EchoCartMCPClient = defaultMcpClient) {
    this.client = client;
  }

  public setUserToken(token: string) {
    this.currentUserToken = token;
  }

  public getUserToken(): string {
    return this.currentUserToken;
  }

  /**
   * Main entrypoint: Processes user prompt, executes tool if required,
   * detects MCP Apps _meta.ui.resourceUri, and synthesizes conversational answer.
   */
  public async processPrompt(prompt: string): Promise<AgentExecutionStep> {
    const startTime = performance.now();
    const normalized = prompt.trim().toLowerCase();
    const stepId = "step-" + Date.now();
    const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

    // Ensure client is initialized
    if (!this.client.isConnected) {
      try {
        await this.client.initialize();
      } catch (err: any) {
        return {
          id: stepId,
          timestamp,
          userPrompt: prompt,
          intent: "error",
          assistantResponse: `I couldn't connect to the EchoCart MCP server at ${this.client.getBaseUrl()}. Please ensure the backend is running. (${err.message})`,
        };
      }
    }

    // 1. Check for Order Tracking Intent
    const orderMatch = normalized.match(/(track|order|delivery|package|status).*(ord-?\d+)/i) ||
                       normalized.match(/(ord-\d+)/i);
    if (orderMatch) {
      const orderId = (orderMatch[2] || orderMatch[1]).toUpperCase();
      return await this.executeToolStep(stepId, timestamp, prompt, "track_order", "get_order_status", {
        order_id: orderId,
        user_token: this.currentUserToken,
      }, startTime);
    }

    // 2. Check for Promotions / Coupons Intent
    if (normalized.includes("promo") || normalized.includes("discount") || normalized.includes("coupon") || normalized.includes("sale") || normalized.includes("deal")) {
      return await this.readResourceStep(stepId, timestamp, prompt, "promotions", "resource://store/promotions/current", startTime);
    }

    // 3. Check for Return Policy Intent
    if (normalized.includes("return") || normalized.includes("warranty") || normalized.includes("refund")) {
      return await this.readResourceStep(stepId, timestamp, prompt, "return_policy", "resource://store/policies/returns", startTime);
    }

    // 4. Check for Cart Operations Intent
    if (normalized.includes("cart") || normalized.includes("buy") || normalized.includes("add") || normalized.includes("checkout")) {
      // 4a. View Cart
      if (normalized.includes("show") || normalized.includes("view") || normalized.includes("open") || normalized.includes("what's in") || normalized.includes("checkout")) {
        // Trigger manage_cart with update of existing or query cart
        return await this.executeToolStep(stepId, timestamp, prompt, "view_cart", "manage_cart", {
          action: "update",
          sku: "ECHO-PRO-01",
          quantity: 1,
          user_token: this.currentUserToken,
        }, startTime, "ui://echocart/cart-view.html");
      }

      // 4b. Remove from Cart
      if (normalized.includes("remove") || normalized.includes("delete")) {
        const sku = this.extractSkuFromText(normalized) || "ECHO-PRO-01";
        return await this.executeToolStep(stepId, timestamp, prompt, "remove_from_cart", "manage_cart", {
          action: "remove",
          sku,
          quantity: 0,
          user_token: this.currentUserToken,
        }, startTime);
      }

      // 4c. Add to Cart
      if (normalized.includes("add")) {
        const sku = this.extractSkuFromText(normalized) || "ECHO-PRO-01";
        const qtyMatch = normalized.match(/(\d+)\s*(of\s*)?(item|pair|pieces|unit)?/);
        const qty = qtyMatch ? parseInt(qtyMatch[1], 10) : 1;

        return await this.executeToolStep(stepId, timestamp, prompt, "add_to_cart", "manage_cart", {
          action: "add",
          sku,
          quantity: qty,
          user_token: this.currentUserToken,
        }, startTime);
      }
    }

    // 5. Default to Catalog Search Intent
    let searchQuery = prompt;
    let category: string | undefined = undefined;

    // Detect category filters
    if (normalized.includes("audio") || normalized.includes("headphone") || normalized.includes("earbud")) {
      category = "audio";
    } else if (normalized.includes("home") || normalized.includes("soundbar")) {
      category = "home";
    } else if (normalized.includes("wearable") || normalized.includes("watch")) {
      category = "wearables";
    } else if (normalized.includes("charger") || normalized.includes("power") || normalized.includes("mic")) {
      category = "electronics";
    }

    // Clean search query from voice wake words
    searchQuery = searchQuery
      .replace(/^alexa,?\s*/i, "")
      .replace(/^(search|find|show me|look for|browse)\s*/i, "")
      .trim();

    return await this.executeToolStep(stepId, timestamp, prompt, "search_catalog", "search_catalog", {
      query: searchQuery || "",
      category,
    }, startTime);
  }

  private extractSkuFromText(text: string): string | null {
    if (text.includes("echo-pro") || text.includes("headphone") || text.includes("pro")) return "ECHO-PRO-01";
    if (text.includes("echo-ear") || text.includes("earbud") || text.includes("earphones")) return "ECHO-EAR-02";
    if (text.includes("echo-spk") || text.includes("soundbar") || text.includes("speaker") || text.includes("hub")) return "ECHO-SPK-03";
    if (text.includes("echo-mic") || text.includes("mic") || text.includes("microphone")) return "ECHO-MIC-04";
    if (text.includes("echo-pwr") || text.includes("charger") || text.includes("pad") || text.includes("magcharge")) return "ECHO-PWR-05";
    if (text.includes("echo-wch") || text.includes("watch") || text.includes("kinetic")) return "ECHO-WCH-06";
    return null;
  }

  /**
   * Executes a tool via MCP Client and handles MCP Apps UI detection
   */
  private async executeToolStep(
    stepId: string,
    timestamp: string,
    prompt: string,
    intent: string,
    toolName: string,
    args: Record<string, any>,
    startTime: number,
    forcedUiUri?: string
  ): Promise<AgentExecutionStep> {
    try {
      const toolResult = await this.client.callTool(toolName, args);
      const latencyMs = Math.round(performance.now() - startTime);

      // Parse structured JSON from content[0]
      let rawPayload: any = null;
      let voiceSummary = "";

      if (toolResult.content && toolResult.content.length > 0) {
        try {
          rawPayload = JSON.parse(toolResult.content[0].text);
        } catch {
          rawPayload = toolResult.content[0].text;
        }

        // Voice summary in content[1] for progressive enhancement
        if (toolResult.content.length > 1 && toolResult.content[1].text) {
          voiceSummary = toolResult.content[1].text;
        }
      }

      // Detect UI Resource URI from tool result or tool definition metadata
      let uiResourceUri = forcedUiUri || toolResult._meta?.ui?.resourceUri;
      if (!uiResourceUri) {
        const toolDef = this.client.tools.find((t) => t.name === toolName);
        uiResourceUri = toolDef?._meta?.ui?.resourceUri;
      }

      // Generate conversational assistant response
      let assistantResponse = voiceSummary;
      if (!assistantResponse) {
        assistantResponse = this.synthesizeResponse(toolName, args, rawPayload);
      }

      return {
        id: stepId,
        timestamp,
        userPrompt: prompt,
        intent,
        toolCall: {
          name: toolName,
          args,
          latencyMs,
        },
        toolResult,
        rawPayload,
        uiResourceUri,
        assistantResponse,
      };
    } catch (err: any) {
      return {
        id: stepId,
        timestamp,
        userPrompt: prompt,
        intent: "error",
        toolCall: {
          name: toolName,
          args,
          latencyMs: Math.round(performance.now() - startTime),
        },
        assistantResponse: `I ran into an issue while calling ${toolName}: ${err.message}`,
      };
    }
  }

  /**
   * Reads an MCP resource and synthesizes conversational response
   */
  private async readResourceStep(
    stepId: string,
    timestamp: string,
    prompt: string,
    intent: string,
    resourceUri: string,
    startTime: number
  ): Promise<AgentExecutionStep> {
    try {
      const readResult = await this.client.readResource(resourceUri);
      const latencyMs = Math.round(performance.now() - startTime);

      let textContent = "";
      if (readResult.contents && readResult.contents[0]) {
        textContent = readResult.contents[0].text || "";
      }

      let assistantResponse = "";
      if (intent === "promotions") {
        try {
          const promoData = JSON.parse(textContent);
          const activeCodes = (promoData.promotions || [])
            .map((p: any) => `${p.code} (${p.description})`)
            .join(", ");
          assistantResponse = `Here are today's active promotions: ${activeCodes}. Apply them at checkout to save!`;
        } catch {
          assistantResponse = textContent;
        }
      } else {
        assistantResponse = textContent.split("\n")[0] || textContent;
      }

      return {
        id: stepId,
        timestamp,
        userPrompt: prompt,
        intent,
        toolCall: {
          name: "resources/read",
          args: { uri: resourceUri },
          latencyMs,
        },
        rawPayload: textContent,
        assistantResponse,
      };
    } catch (err: any) {
      return {
        id: stepId,
        timestamp,
        userPrompt: prompt,
        intent: "error",
        assistantResponse: `Failed to load store policy or promotions: ${err.message}`,
      };
    }
  }

  private synthesizeResponse(toolName: string, args: Record<string, any>, payload: any): string {
    if (toolName === "search_catalog") {
      if (Array.isArray(payload) && payload.length > 0) {
        return `I found ${payload.length} products matching "${args.query || 'catalog'}". Check the display to explore details.`;
      }
      return `I couldn't find any products matching "${args.query}". Try searching for audio, wearables, or soundbars.`;
    }

    if (toolName === "manage_cart") {
      if (payload?.cart) {
        return `Your cart now has ${payload.cart.total_items} items with an estimated total of $${Number(payload.cart.total_price).toFixed(2)}.`;
      }
      return payload?.message || "Your cart has been updated.";
    }

    if (toolName === "get_order_status") {
      if (payload?.order_id) {
        return `Order ${payload.order_id} is currently ${payload.status} with ${payload.carrier || 'carrier'}. Estimated delivery: ${payload.estimated_delivery || 'soon'}.`;
      }
      return "I retrieved your order details. Delivery is progressing normally.";
    }

    return "Done! The display has updated with the latest information.";
  }
}

export const defaultAgentEngine = new EchoCartAgentEngine(defaultMcpClient);
