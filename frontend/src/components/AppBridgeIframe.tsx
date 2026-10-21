"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { defaultMcpClient } from "@/lib/mcpClient";
import { Maximize2, Minimize2, Terminal, Shield, RefreshCw } from "lucide-react";

interface WireEventLog {
  id: string;
  time: string;
  direction: "IN" | "OUT";
  method: string;
  payload: any;
}

interface AppBridgeIframeProps {
  resourceUri?: string;
  initialData?: any;
  mcpBaseUrl?: string;
  onToolExecuted?: (toolName: string, args: any, result: any) => void;
  title?: string;
}

export const AppBridgeIframe: React.FC<AppBridgeIframeProps> = ({
  resourceUri = "ui://echocart/cart-view.html",
  initialData,
  mcpBaseUrl = "http://127.0.0.1:8080",
  onToolExecuted,
  title,
}) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [wireLogs, setWireLogs] = useState<WireEventLog[]>([]);
  const [showInspector, setShowInspector] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);

  // Convert ui://echocart/<template>.html to HTTP endpoint on MCP server
  const resolveTemplateUrl = useCallback(
    (uri: string): string => {
      const cleanBase = mcpBaseUrl.replace(/\/+$/, "");
      const cleanUri = uri.replace("ui://echocart/", "").replace("ui://", "");
      return `${cleanBase}/mcp-apps/${cleanUri}`;
    },
    [mcpBaseUrl]
  );

  const targetUrl = resolveTemplateUrl(resourceUri);

  const addWireLog = useCallback((direction: "IN" | "OUT", method: string, payload: any) => {
    const time = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    setWireLogs((prev) => [
      {
        id: "log-" + Date.now() + "-" + Math.random().toString(36).substring(2, 5),
        time,
        direction,
        method,
        payload,
      },
      ...prev.slice(0, 49),
    ]);
  }, []);

  // PostMessage Bridge listener
  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      const data = event.data;
      if (!data || typeof data !== "object" || data.jsonrpc !== "2.0") return;

      const iframeWindow = iframeRef.current?.contentWindow;
      // Only process messages from our iframe
      if (iframeWindow && event.source !== iframeWindow) return;

      addWireLog("IN", data.method || `resp:${data.id}`, data);

      // 1. Handle Handshake: ui/initialize
      if (data.method === "ui/initialize") {
        const initResponse = {
          jsonrpc: "2.0",
          id: data.id,
          result: {
            protocolVersion: "2025-11-25",
            hostInfo: { name: "EchoCart-AlexaPlus-Host", version: "2.0.0" },
          },
        };
        iframeWindow?.postMessage(initResponse, "*");
        addWireLog("OUT", `resp:${data.id}`, initResponse);

        // Push initial tool state into the iframe view
        if (initialData) {
          const stateUpdate = {
            jsonrpc: "2.0",
            method: "ui/tool-result",
            params: initialData,
          };
          iframeWindow?.postMessage(stateUpdate, "*");
          addWireLog("OUT", "ui/tool-result", stateUpdate);
        }
        return;
      }

      // 2. Handle Tools Call Request from Guest View (e.g. manage_cart)
      if (data.method === "tools/call" && data.params?.name) {
        const toolName = data.params.name;
        const toolArgs = data.params.arguments || {};

        try {
          // Execute against backend MCP server via streamable HTTP
          const toolResult = await defaultMcpClient.callTool(toolName, toolArgs);

          // Parse raw JSON from tool result content[0]
          let parsedData: any = null;
          if (toolResult.content && toolResult.content[0]?.text) {
            try {
              parsedData = JSON.parse(toolResult.content[0].text);
            } catch {
              parsedData = toolResult.content[0].text;
            }
          }

          // Reply with JSON-RPC RPC success response
          const rpcSuccess = {
            jsonrpc: "2.0",
            id: data.id,
            result: toolResult,
          };
          iframeWindow?.postMessage(rpcSuccess, "*");
          addWireLog("OUT", `resp:${data.id}`, rpcSuccess);

          // Dispatch updated tool result notification so the view refreshes state
          if (parsedData) {
            const pushNotification = {
              jsonrpc: "2.0",
              method: "ui/tool-result",
              params: parsedData,
            };
            iframeWindow?.postMessage(pushNotification, "*");
            addWireLog("OUT", "ui/tool-result", pushNotification);
          }

          // Notify parent app of interactive update
          if (onToolExecuted) {
            onToolExecuted(toolName, toolArgs, parsedData || toolResult);
          }
        } catch (err: any) {
          const rpcError = {
            jsonrpc: "2.0",
            id: data.id,
            error: {
              code: -32603,
              message: err.message || "Internal tool execution error",
            },
          };
          iframeWindow?.postMessage(rpcError, "*");
          addWireLog("OUT", `err:${data.id}`, rpcError);
        }
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [addWireLog, initialData, onToolExecuted]);

  // When initialData changes from parent, notify the iframe
  useEffect(() => {
    if (initialData && iframeRef.current?.contentWindow) {
      const stateUpdate = {
        jsonrpc: "2.0",
        method: "ui/tool-result",
        params: initialData,
      };
      iframeRef.current.contentWindow.postMessage(stateUpdate, "*");
      addWireLog("OUT", "ui/tool-result", stateUpdate);
    }
  }, [initialData, addWireLog]);

  return (
    <div
      className={`flex flex-col bg-slate-900/90 border border-slate-700/60 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-xl transition-all duration-300 ${
        isFullscreen ? "fixed inset-4 z-50" : "w-full h-full min-h-[580px]"
      }`}
    >
      {/* Top Ambient Bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-950/70 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-400 text-xs font-mono font-medium">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span>{resourceUri}</span>
          </div>
          <div className="flex items-center gap-1 text-[11px] text-emerald-400/90 font-medium px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/20">
            <Shield className="w-3 h-3" />
            <span>sandboxed iframe</span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIframeKey((k) => k + 1)}
            title="Reload View"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowInspector(!showInspector)}
            title="Toggle Wire Inspector"
            className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border transition ${
              showInspector
                ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
                : "bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-700"
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Wire ({wireLogs.length})</span>
          </button>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Sandboxed Iframe Container */}
      <div className="relative flex-1 w-full h-full min-h-[460px] bg-slate-950">
        <iframe
          key={iframeKey}
          ref={iframeRef}
          src={targetUrl}
          sandbox="allow-scripts allow-forms allow-same-origin"
          title={title || "MCP Sandboxed Interactive View"}
          className="w-full h-full border-0 block"
        />
      </div>

      {/* Live PostMessage Wire Protocol Inspector */}
      {showInspector && (
        <div className="border-t border-slate-800 bg-slate-950/95 p-3 flex flex-col gap-2 max-h-48 overflow-y-auto font-mono text-[11px]">
          <div className="flex justify-between items-center text-slate-400 font-semibold text-xs border-b border-slate-800 pb-1">
            <span>window.postMessage Wire Inspector</span>
            <span className="text-cyan-400">@modelcontextprotocol/ext-apps</span>
          </div>
          {wireLogs.length === 0 ? (
            <div className="text-slate-500 italic py-2">No postMessage frames recorded yet...</div>
          ) : (
            wireLogs.map((log) => (
              <div
                key={log.id}
                className="flex items-start gap-2 py-1 px-2 rounded bg-slate-900/60 border border-slate-800/70 text-slate-300"
              >
                <span className="text-slate-500 text-[10px] whitespace-nowrap">{log.time}</span>
                <span
                  className={`font-bold text-[10px] px-1 rounded ${
                    log.direction === "IN"
                      ? "bg-emerald-950 text-emerald-400 border border-emerald-500/30"
                      : "bg-cyan-950 text-cyan-400 border border-cyan-500/30"
                  }`}
                >
                  {log.direction}
                </span>
                <span className="font-semibold text-slate-200">{log.method}:</span>
                <span className="text-slate-400 truncate max-w-md">
                  {JSON.stringify(log.payload)}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
