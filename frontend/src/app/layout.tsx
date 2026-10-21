import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "EchoCart Nexus - Alexa+ Multimodal Smart Display",
  description:
    "Simulated Amazon Echo Show smart display interface orchestrating user voice commands, LLM tool execution, and MCP Apps sandboxed UI cards over Streamable HTTP.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full bg-slate-950 text-slate-100 antialiased dark`}
    >
      <body className="min-h-full flex flex-col bg-[#070B11]">{children}</body>
    </html>
  );
}
