/**
 * EchoCart Nexus - Streamable HTTP MCP Client
 * Implements JSON-RPC 2.0 communication over Streamable HTTP adhering to:
 * - Specification: MCP-Protocol-Version: 2025-11-25
 * - Mcp-Method and Mcp-Name header mirroring
 * - MCP Apps extension metadata discovery (_meta.ui.resourceUri)
 */

export const MCP_PROTOCOL_VERSION = "2025-11-25";

export interface MCPToolMetaUI {
  resourceUri?: string;
  csp?: {
    connectDomains?: string[];
    resourceDomains?: string[];
    frameDomains?: string[];
    baseUriDomains?: string[];
  };
}

export interface MCPTool {
  name: string;
  title?: string;
  description?: string;
  inputSchema: {
    type: string;
    properties?: Record<string, any>;
    required?: string[];
    additionalProperties?: boolean;
  };
  _meta?: {
    ui?: MCPToolMetaUI;
    [key: string]: any;
  };
}

export interface MCPResource {
  uri: string;
  name: string;
  mimeType?: string;
  description?: string;
  _meta?: {
    ui?: MCPToolMetaUI;
    [key: string]: any;
  };
}

export interface MCPPrompt {
  name: string;
  description?: string;
  arguments?: Array<{
    name: string;
    description?: string;
    required?: boolean;
  }>;
}

export interface MCPTextContent {
  type: "text";
  text: string;
}

export interface MCPCallToolResult {
  content: Array<MCPTextContent | { type: string; [key: string]: any }>;
  _meta?: {
    ui?: MCPToolMetaUI;
    [key: string]: any;
  };
  isError?: boolean;
}

export interface MCPJsonRpcResponse<T = any> {
  jsonrpc: "2.0";
  id: string | number;
  result?: T;
  error?: {
    code: number;
    message: string;
    data?: any;
  };
}

export class EchoCartMCPClient {
  private baseUrl: string;
  public isConnected: boolean = false;
  public tools: MCPTool[] = [];
  public resources: MCPResource[] = [];
  public prompts: MCPPrompt[] = [];
  public serverInfo: { name?: string; version?: string } = {};

  constructor(baseUrl: string = "http://127.0.0.1:8080") {
    // Strip trailing slash
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  public setBaseUrl(newUrl: string) {
    this.baseUrl = newUrl.replace(/\/+$/, "");
    this.isConnected = false;
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * Helper to perform standard JSON-RPC 2.0 requests over Streamable HTTP
   * injecting all required wire protocol headers.
   */
  private async postRpc<T = any>(
    method: string,
    params?: Record<string, any>,
    targetName?: string
  ): Promise<T> {
    const rpcId = "req-" + Date.now() + "-" + Math.random().toString(36).substring(2, 6);
    const payload = {
      jsonrpc: "2.0",
      id: rpcId,
      method,
      params: params || {},
    };

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
      "Mcp-Method": method,
    };

    if (targetName) {
      headers["Mcp-Name"] = targetName;
    }

    const endpoint = `${this.baseUrl}/mcp`;
    const response = await fetch(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorJson = JSON.parse(errorText);
        if (errorJson.error?.message) {
          errorMsg = errorJson.error.message;
        }
      } catch {
        if (errorText) errorMsg += ` - ${errorText.substring(0, 100)}`;
      }
      throw new Error(`MCP Server Error (${endpoint}): ${errorMsg}`);
    }

    const rawText = await response.text();
    let rpcResp: MCPJsonRpcResponse<T> | null = null;

    // Handle Streamable HTTP SSE (event: message\ndata: {...})
    for (const line of rawText.split("\n")) {
      const trimmed = line.trim();
      if (trimmed.startsWith("data:")) {
        const dataStr = trimmed.substring(5).trim();
        if (dataStr) {
          rpcResp = JSON.parse(dataStr);
          break;
        }
      }
    }

    // Direct JSON response fallback
    if (!rpcResp) {
      try {
        rpcResp = JSON.parse(rawText);
      } catch (err) {
        throw new Error(`Failed to parse MCP response as JSON or SSE stream: ${rawText.substring(0, 150)}`);
      }
    }

    if (!rpcResp) {
      throw new Error("Empty JSON-RPC response from MCP server.");
    }

    if (rpcResp.error) {
      throw new Error(`MCP RPC Error [${rpcResp.error.code}]: ${rpcResp.error.message}`);
    }

    return rpcResp.result as T;
  }

  /**
   * Handshake: Initialize MCP protocol connection
   */
  public async initialize(): Promise<{ serverInfo: any; protocolVersion: string }> {
    try {
      const result = await this.postRpc<{
        protocolVersion: string;
        capabilities: any;
        serverInfo: { name: string; version: string };
      }>("initialize", {
        protocolVersion: MCP_PROTOCOL_VERSION,
        capabilities: {
          tools: { listChanged: true },
          resources: { subscribe: true },
          prompts: { listChanged: true },
        },
        clientInfo: {
          name: "EchoCart-AlexaPlus-Host",
          version: "2.0.0",
        },
      });

      this.isConnected = true;
      this.serverInfo = result.serverInfo || {};

      // Send initialized notification
      try {
        await this.postRpc("notifications/initialized", {});
      } catch (e) {
        // Notification fire-and-forget
      }

      // Automatically discover primitives
      await Promise.allSettled([
        this.listTools(),
        this.listResources(),
        this.listPrompts(),
      ]);

      return {
        serverInfo: this.serverInfo,
        protocolVersion: result.protocolVersion,
      };
    } catch (err: any) {
      this.isConnected = false;
      throw err;
    }
  }

  /**
   * Discover available tools and UI metadata
   */
  public async listTools(): Promise<MCPTool[]> {
    const res = await this.postRpc<{ tools: MCPTool[] }>("tools/list");
    this.tools = res.tools || [];
    return this.tools;
  }

  /**
   * Discover registered resources
   */
  public async listResources(): Promise<MCPResource[]> {
    const res = await this.postRpc<{ resources: MCPResource[] }>("resources/list");
    this.resources = res.resources || [];
    return this.resources;
  }

  /**
   * Read resource contents by URI
   */
  public async readResource(uri: string): Promise<any> {
    return await this.postRpc("resources/read", { uri }, uri);
  }

  /**
   * Discover prompts
   */
  public async listPrompts(): Promise<MCPPrompt[]> {
    const res = await this.postRpc<{ prompts: MCPPrompt[] }>("prompts/list");
    this.prompts = res.prompts || [];
    return this.prompts;
  }

  /**
   * Execute tool with structured arguments
   */
  public async callTool(name: string, args: Record<string, any>): Promise<MCPCallToolResult> {
    return await this.postRpc<MCPCallToolResult>(
      "tools/call",
      {
        name,
        arguments: args,
      },
      name
    );
  }

  /**
   * Health ping
   */
  public async ping(): Promise<boolean> {
    try {
      await this.postRpc("ping");
      this.isConnected = true;
      return true;
    } catch {
      this.isConnected = false;
      return false;
    }
  }
}

// Singleton instance for client-side usage
export const defaultMcpClient = new EchoCartMCPClient(
  process.env.NEXT_PUBLIC_MCP_SERVER_URL || "http://127.0.0.1:8080"
);
