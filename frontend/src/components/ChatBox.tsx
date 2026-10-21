"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, Mic, Volume2, VolumeX, Sparkles, Wrench, Clock, CheckCircle2 } from "lucide-react";
import { AgentExecutionStep } from "@/lib/agentEngine";

interface ChatBoxProps {
  steps: AgentExecutionStep[];
  onSendMessage: (text: string) => Promise<void>;
  isLoading: boolean;
}

export const ChatBox: React.FC<ChatBoxProps> = ({
  steps,
  onSendMessage,
  isLoading,
}) => {
  const [inputText, setInputText] = useState("");
  const [speechEnabled, setSpeechEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps, isLoading]);

  // Voice speech synthesis
  useEffect(() => {
    if (!speechEnabled || steps.length === 0) return;
    const lastStep = steps[steps.length - 1];
    if (lastStep && lastStep.assistantResponse && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(lastStep.assistantResponse);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  }, [steps, speechEnabled]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;
    const msg = inputText.trim();
    setInputText("");
    await onSendMessage(msg);
  };

  const handleMicClick = () => {
    // Check for Web Speech API recognition
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      setIsListening(true);
      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          onSendMessage(transcript);
        }
        setIsListening(false);
      };
      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);
      recognition.start();
    } else {
      // Simulate quick voice query
      const sampleQueries = [
        "Alexa, show my shopping cart",
        "Alexa, search for noise cancelling headphones",
        "Alexa, add pro headphones to cart",
        "Alexa, what are today's promotions?",
        "Alexa, track order ORD-98241",
      ];
      const randomQuery = sampleQueries[Math.floor(Math.random() * sampleQueries.length)];
      onSendMessage(randomQuery);
    }
  };

  const sampleChips = [
    { label: "View Cart", query: "Alexa, show my shopping cart" },
    { label: "Search Audio", query: "Alexa, search headphones" },
    { label: "+ Pro Headphones", query: "Alexa, add pro headphones to my cart" },
    { label: "Track Package", query: "Alexa, track order ORD-98241" },
    { label: "Active Deals", query: "Alexa, what promotions are active?" },
  ];

  return (
    <div className="flex flex-col h-full bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur-xl shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-950/80 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="font-semibold text-sm text-slate-200">Alexa+ Voice Transcript</span>
        </div>
        <button
          onClick={() => setSpeechEnabled(!speechEnabled)}
          title={speechEnabled ? "Mute Voice Speech" : "Enable Voice Speech"}
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition ${
            speechEnabled
              ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
              : "bg-slate-800/80 text-slate-400 border-slate-700 hover:text-slate-200"
          }`}
        >
          {speechEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
          <span>{speechEnabled ? "Voice ON" : "Voice OFF"}</span>
        </button>
      </div>

      {/* Transcript Scroll Area */}
      <div ref={scrollRef} className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
        {steps.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-6 text-slate-400 gap-3 my-auto">
            <div className="w-12 h-12 rounded-2xl bg-cyan-950/60 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-lg shadow-cyan-950/40">
              <Sparkles className="w-6 h-6" />
            </div>
            <div className="font-semibold text-slate-200 text-sm">EchoCart Assistant Ready</div>
            <p className="text-xs text-slate-400 max-w-xs leading-relaxed">
              Speak or type commerce commands to browse catalog gear, update your shopping cart, or track live orders.
            </p>
          </div>
        ) : (
          steps.map((step) => (
            <div key={step.id} className="flex flex-col gap-2">
              {/* User Bubble */}
              <div className="self-end max-w-[85%] bg-cyan-600/20 border border-cyan-500/30 text-cyan-50 px-3.5 py-2.5 rounded-2xl rounded-tr-sm text-sm shadow-md">
                <div className="text-[10px] text-cyan-400/80 font-mono mb-1">{step.timestamp} • User</div>
                <div>{step.userPrompt}</div>
              </div>

              {/* Tool Execution Diagnostic Pill */}
              {step.toolCall && (
                <div className="self-start flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-950/70 border border-slate-800 text-[11px] text-slate-400 font-mono">
                  <Wrench className="w-3 h-3 text-cyan-400" />
                  <span className="text-cyan-300 font-medium">{step.toolCall.name}</span>
                  <span className="text-slate-500">({step.toolCall.latencyMs}ms)</span>
                  <CheckCircle2 className="w-3 h-3 text-emerald-400 ml-1" />
                </div>
              )}

              {/* Alexa Assistant Bubble */}
              <div className="self-start max-w-[90%] bg-slate-800/70 border border-slate-700/60 text-slate-100 px-4 py-3 rounded-2xl rounded-tl-sm text-sm shadow-md flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5 text-[10px] text-cyan-400 font-semibold uppercase tracking-wider">
                  <div className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  <span>Alexa+</span>
                </div>
                <div className="leading-relaxed">{step.assistantResponse}</div>
              </div>
            </div>
          ))
        )}

        {/* Loading Spinner */}
        {isLoading && (
          <div className="self-start flex items-center gap-2 px-4 py-3 rounded-2xl bg-slate-800/50 border border-slate-700/50 text-slate-300 text-sm">
            <div className="flex gap-1 items-center">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            <span className="text-xs text-slate-400">Alexa is executing MCP tool...</span>
          </div>
        )}
      </div>

      {/* Suggested Quick Prompt Chips */}
      <div className="px-3 py-2 bg-slate-950/60 border-t border-slate-800/60 flex items-center gap-2 overflow-x-auto scrollbar-none">
        {sampleChips.map((chip, idx) => (
          <button
            key={idx}
            onClick={() => onSendMessage(chip.query)}
            disabled={isLoading}
            className="text-[11px] font-medium text-slate-300 bg-slate-800/60 hover:bg-slate-700 border border-slate-700/70 hover:border-cyan-500/50 rounded-full px-3 py-1 whitespace-nowrap transition"
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* Input Field & Mic Bar */}
      <form onSubmit={handleSubmit} className="p-3 bg-slate-950/90 border-t border-slate-800 flex items-center gap-2">
        <button
          type="button"
          onClick={handleMicClick}
          disabled={isLoading}
          title="Voice Command (Tap to Speak)"
          className={`p-2.5 rounded-xl border transition ${
            isListening
              ? "bg-rose-500/20 text-rose-400 border-rose-500/50 animate-pulse"
              : "bg-slate-800/80 text-cyan-400 border-slate-700 hover:bg-slate-700 hover:text-cyan-300"
          }`}
        >
          <Mic className="w-4 h-4" />
        </button>

        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Say 'Alexa, search headphones' or type..."
          disabled={isLoading}
          className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 transition"
        />

        <button
          type="submit"
          disabled={!inputText.trim() || isLoading}
          className="p-2.5 rounded-xl bg-cyan-500 text-slate-950 font-bold hover:bg-cyan-400 disabled:opacity-40 disabled:hover:bg-cyan-500 transition shadow-lg shadow-cyan-500/20"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};
