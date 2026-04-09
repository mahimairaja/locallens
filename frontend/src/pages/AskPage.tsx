import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Trash2, Loader2, AlertCircle } from "lucide-react";
import type { ChatMessage, AskSource } from "@/types";

const SUGGESTED_QUESTIONS = [
  "What are the key points in my latest report?",
  "Find all files mentioning revenue or sales",
  "Summarize my meeting notes from this month",
  "What code files deal with authentication?",
];

export default function AskPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const askQuestion = async (question: string) => {
    if (!question.trim() || isStreaming) return;
    setError(null);

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, top_k: 3 }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
      }

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let sources: AskSource[] = [];

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              continue;
            }
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              try {
                const parsed = JSON.parse(data);
                if (parsed.text !== undefined) {
                  setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    if (last.role === "assistant") {
                      last.content += parsed.text;
                    }
                    return updated;
                  });
                }
                if (parsed.sources) {
                  sources = parsed.sources;
                }
              } catch {
                // ignore parse errors
              }
            }
          }
        }
      }

      // Attach sources to the assistant message
      if (sources.length > 0) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            last.sources = sources;
          }
          return updated;
        });
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      const msg = err instanceof Error ? err.message : "Unknown error";
      if (msg.toLowerCase().includes("ollama") || msg.toLowerCase().includes("connect")) {
        setError("Ollama is not running. Start it with: ollama serve");
      } else {
        setError(msg);
      }
      // Remove empty assistant message on error
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && !last.content) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  const clearChat = () => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col">
      {/* Header with Clear */}
      <div className="mb-4 flex items-center justify-end">
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearChat}>
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Clear Chat
          </Button>
        )}
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center space-y-6 py-20">
            <p className="text-lg text-muted-foreground">
              Ask a question about your indexed files
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <Card
                  key={q}
                  className="cursor-pointer transition-colors hover:border-primary/50"
                  onClick={() => askQuestion(q)}
                >
                  <CardContent className="p-4 text-sm">{q}</CardContent>
                </Card>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4 pb-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-4 py-3 text-sm ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-card border border-border"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  {msg.role === "assistant" && isStreaming && msg === messages[messages.length - 1] && !msg.content && (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border pt-2">
                      {msg.sources.map((src, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {src.file_name}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Error Banner */}
      {error && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
          {error.includes("No files indexed") && (
            <Link to="/index" className="ml-auto text-primary underline">
              Index files
            </Link>
          )}
        </div>
      )}

      {/* Input */}
      <div className="flex items-center gap-2 border-t border-border pt-4">
        <Input
          placeholder="Ask a question..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
              e.preventDefault();
              askQuestion(input);
            }
          }}
          disabled={isStreaming}
          className="flex-1"
        />
        <Button onClick={() => askQuestion(input)} disabled={isStreaming || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <p className="mt-1 text-xs text-muted-foreground text-right">
        Press Enter to send
      </p>
    </div>
  );
}
