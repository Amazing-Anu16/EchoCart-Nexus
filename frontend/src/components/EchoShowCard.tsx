"use client";

import React, { useState, useEffect } from "react";
import { AppBridgeIframe } from "./AppBridgeIframe";
import { ChatBox } from "./ChatBox";
import { AgentExecutionStep, defaultAgentEngine } from "@/lib/agentEngine";
import { defaultMcpClient } from "@/lib/mcpClient";
import {
  Wifi,
  CloudSun,
  Layers,
  ShoppingBag,
  SlidersHorizontal,
  CircleCheck,
  CircleAlert,
  Server,
  Settings,
} from "lucide-react";

export const EchoShowCard: React.FC = () => {
  const [steps, setSteps] = useState<AgentExecutionStep[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentTime, setCurrentTime] = useState("");
  const [currentDate, setCurrentDate] = useState("");
  const [isServerConnected, setIsServerConnected] = useState(false);
  const [serverUrl, setServerUrl] = useState("http://127.0.0.1:8080");
  const [showConfig, setShowConfig] = useState(false);

  // Active Multimodal Visual Resource
  const [activeUiUri, setActiveUiUri] = useState<string>("ui://echocart/cart-view.html");
  const [activePayload, setActivePayload] = useState<any>(null);

  // Live Clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
      setCurrentDate(
        now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Check MCP Server Health on mount
  useEffect(() => {
    let mounted = true;
    const checkConnection = async () => {
      try {
        defaultMcpClient.setBaseUrl(serverUrl);
        await defaultMcpClient.initialize();
        if (mounted) setIsServerConnected(true);
      } catch {
        if (mounted) setIsServerConnected(false);
      }
    };
    checkConnection();
    return () => {
      mounted = false;
    };
  }, [serverUrl]);

  // Handle incoming user prompts
  const handleSendMessage = async (text: string) => {
    setIsLoading(true);
    try {
      const step = await defaultAgentEngine.processPrompt(text);
      setSteps((prev) => [...prev, step]);

      // If the tool execution returned or bound a UI resource, update the display!
      if (step.uiResourceUri) {
        setActiveUiUri(step.uiResourceUri);
        if (step.rawPayload) {
          setActivePayload(step.rawPayload);
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Callback when a user clicks buttons inside the sandboxed iframe
  const handleIframeToolExecution = (toolName: string, args: any, result: any) => {
    // Generate a transcript entry for the direct touch interaction
    const actionDesc =
      toolName === "manage_cart"
        ? `Tapped ${args.action} on ${args.sku} (Qty: ${args.quantity})`
        : `Invoked ${toolName}`;

    const newStep: AgentExecutionStep = {
      id: "touch-" + Date.now(),
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }),
      userPrompt: `[Touch Interaction] ${actionDesc}`,
      intent: "touch_interaction",
      toolCall: {
        name: toolName,
        args,
        latencyMs: 45,
      },
      rawPayload: result,
      assistantResponse:
        result?.message ||
        `Updated ${args.sku}. Your cart now has ${result?.cart?.total_items || 0} items totaling $${Number(
          result?.cart?.total_price || 0
        ).toFixed(2)}.`,
    };

    setSteps((prev) => [...prev, newStep]);
    setActivePayload(result);
  };

  return (
    <div className="w-full max-w-[1400px] h-[92vh] max-h-[960px] bg-slate-950/90 rounded-[28px] border-4 border-slate-800 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.9),0_0_50px_rgba(0,202,255,0.15)] flex flex-col overflow-hidden relative backdrop-blur-2xl">
      {/* Top Ambient Alexa Cyan Wave Strip */}
      <div
        className={`h-1.5 w-full bg-gradient-to-r from-transparent via-cyan-400 to-transparent transition-opacity duration-300 ${
          isLoading ? "opacity-100 shadow-[0_0_20px_#00CAFF]" : "opacity-40"
        }`}
      />

      {/* Echo Show Top Status Bar */}
      <header className="px-6 py-3 flex items-center justify-between border-b border-slate-800/80 bg-slate-950/60 text-slate-400 text-xs">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-slate-100 font-semibold text-sm">
            <span className="text-cyan-400 text-base">{currentTime || "12:00 PM"}</span>
            <span className="text-slate-600">•</span>
            <span className="text-slate-300">{currentDate}</span>
          </div>
          <div className="hidden sm:flex items-center gap-1.5 text-slate-400">
            <CloudSun className="w-4 h-4 text-amber-400" />
            <span>72°F Partly Cloudy</span>
          </div>
        </div>

        {/* Server & Status Badges */}
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-medium transition ${
              isServerConnected
                ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/30"
                : "bg-rose-950/40 text-rose-400 border-rose-500/30"
            }`}
          >
            {isServerConnected ? (
              <CircleCheck className="w-3.5 h-3.5" />
            ) : (
              <CircleAlert className="w-3.5 h-3.5" />
            )}
            <span>{isServerConnected ? "MCP Server Online" : "MCP Server Offline"}</span>
          </div>

          <div className="hidden md:flex items-center gap-1.5 text-slate-400 text-xs font-mono">
            <Wifi className="w-3.5 h-3.5 text-cyan-400" />
            <span>Wi-Fi 6</span>
          </div>

          <button
            onClick={() => setShowConfig(!showConfig)}
            title="Configure Server Endpoint"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Settings Drawer */}
      {showConfig && (
        <div className="px-6 py-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-xs gap-4">
          <div className="flex items-center gap-2 text-slate-300">
            <Server className="w-4 h-4 text-cyan-400" />
            <span>MCP Server Endpoint:</span>
            <input
              type="text"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-100 font-mono text-xs w-64 focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                defaultMcpClient.setBaseUrl(serverUrl);
                defaultMcpClient.initialize().then(() => setIsServerConnected(true)).catch(() => setIsServerConnected(false));
              }}
              className="px-3 py-1 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold rounded text-xs transition"
            >
              Reconnect
            </button>
            <button
              onClick={() => setShowConfig(false)}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs transition"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Split-Screen Main Display Body */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-5 p-5 overflow-hidden">
        {/* Left Column: Conversational Transcript & Voice Chat */}
        <div className="lg:col-span-5 h-full flex flex-col min-h-0">
          <ChatBox
            steps={steps}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
          />
        </div>

        {/* Right Column: Multimodal Interactive Visual Stage */}
        <div className="lg:col-span-7 h-full flex flex-col gap-3 min-h-0">
          {/* Visual Bar Selector */}
          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Display Surface
              </span>
              <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-full p-1 text-xs">
                <button
                  onClick={() => setActiveUiUri("ui://echocart/cart-view.html")}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-full font-medium transition ${
                    activeUiUri.includes("cart-view")
                      ? "bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <ShoppingBag className="w-3.5 h-3.5" />
                  <span>Cart Card</span>
                </button>
                <button
                  onClick={() => setActiveUiUri("ui://echocart/product-carousel.html")}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-full font-medium transition ${
                    activeUiUri.includes("product-carousel")
                      ? "bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <SlidersHorizontal className="w-3.5 h-3.5" />
                  <span>Product Slider</span>
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 text-[11px] text-slate-500 font-mono">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span>1080p Ambient Viewport</span>
            </div>
          </div>

          {/* Sandboxed Host Frame */}
          <div className="flex-1 w-full h-full min-h-0">
            <AppBridgeIframe
              resourceUri={activeUiUri}
              initialData={activePayload}
              mcpBaseUrl={serverUrl}
              onToolExecuted={handleIframeToolExecution}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
