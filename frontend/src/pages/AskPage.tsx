import { useState, useRef, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Trash2, Loader2, AlertCircle, Mic, Volume2, Square, AlertTriangle, Search, RotateCcw, Copy } from "lucide-react";
import { api } from "@/lib/api";
import type { ChatMessage, AskSource } from "@/types";

type TtsState = "idle" | "loading" | "playing";

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
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceAvailable, setVoiceAvailable] = useState<{ stt: boolean; tts: boolean }>({ stt: false, tts: false });
  const [ollamaOffline, setOllamaOffline] = useState(false);
  const [ttsStates, setTtsStates] = useState<Record<string, TtsState>>({});
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Probe voice availability once
  useEffect(() => {
    fetch("/api/voice/status")
      .then((r) => r.json())
      .then((data) =>
        setVoiceAvailable({ stt: Boolean(data.stt_available), tts: Boolean(data.tts_available) })
      )
      .catch(() => setVoiceAvailable({ stt: false, tts: false }));

    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      audioRef.current?.pause();
    };
  }, []);

  // Poll health to detect Ollama status
  useEffect(() => {
    async function checkOllama() {
      try {
        const data = await api.checkHealth() as { ollama: string };
        setOllamaOffline(data.ollama !== "ok");
      } catch {
        setOllamaOffline(true);
      }
    }
    checkOllama();
    const interval = setInterval(checkOllama, 30000);
    return () => clearInterval(interval);
  }, []);

  const toggleSources = (msgId: string) => {
    setExpandedSources((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

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
      const res = await fetch(api.askUrl(), {
        method: "POST",
        headers: api.askHeaders(),
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
    audioRef.current?.pause();
    setMessages([]);
    setError(null);
    setTtsStates({});
    setExpandedSources({});
  };

  const startRecording = async () => {
    if (isStreaming || isTranscribing || isRecording) return;
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        await transcribeAndAsk(blob);
      };
      recorder.start();
      setIsRecording(true);
    } catch {
      setError("Microphone access denied or unavailable.");
    }
  };

  const stopRecording = () => {
    if (!isRecording) return;
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  };

  const transcribeAndAsk = async (blob: Blob) => {
    setIsTranscribing(true);
    try {
      const { text } = await api.transcribe(blob);
      const cleaned = (text ?? "").trim();
      if (!cleaned) {
        setError("Didn't catch that -- try speaking again.");
        return;
      }
      await askQuestion(cleaned);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Transcription failed";
      setError(msg);
    } finally {
      setIsTranscribing(false);
    }
  };

  const getTtsState = (id: string): TtsState => ttsStates[id] ?? "idle";

  const setTtsState = (id: string, state: TtsState) =>
    setTtsStates((prev) => ({ ...prev, [id]: state }));

  const playMessage = async (msg: ChatMessage) => {
    if (!voiceAvailable.tts || !msg.content.trim()) return;
    const state = getTtsState(msg.id);

    // Stop if already playing or loading
    if (state === "playing" || state === "loading") {
      audioRef.current?.pause();
      audioRef.current = null;
      setTtsState(msg.id, "idle");
      return;
    }

    try {
      // Stop any other playback first
      audioRef.current?.pause();
      audioRef.current = null;
      // Reset all other playing states
      setTtsStates((prev) => {
        const next: Record<string, TtsState> = {};
        for (const k in prev) next[k] = "idle";
        next[msg.id] = "loading";
        return next;
      });

      const buf = await api.synthesize(msg.content.slice(0, 1000));
      const url = URL.createObjectURL(new Blob([buf], { type: "audio/wav" }));
      const audio = new Audio(url);
      audioRef.current = audio;
      setTtsState(msg.id, "playing");

      audio.onended = () => {
        setTtsState(msg.id, "idle");
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setTtsState(msg.id, "idle");
        URL.revokeObjectURL(url);
      };
      await audio.play();
    } catch {
      setTtsState(msg.id, "idle");
      setError("Could not play audio response.");
    }
  };

  const copyMessage = async (msg: ChatMessage) => {
    try {
      await navigator.clipboard.writeText(msg.content);
    } catch {
      // silent fail
    }
  };

  const retryMessage = (msg: ChatMessage) => {
    // Find the user message right before this assistant message
    const idx = messages.findIndex((m) => m.id === msg.id);
    if (idx > 0 && messages[idx - 1].role === "user") {
      askQuestion(messages[idx - 1].content);
    }
  };

  // Derive sources for the right panel from the latest assistant message that has sources
  const latestSources: AskSource[] = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant" && messages[i].sources && messages[i].sources!.length > 0) {
        return messages[i].sources!;
      }
    }
    return [];
  }, [messages]);

  const inputEmpty = !input.trim();
  const hasMessages = messages.length > 0;

  return (
    <div className="sk-ask-page" style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 7rem)", maxWidth: "1280px", margin: "0 auto", padding: "0 1rem" }}>
      {/* Topbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "12px",
          paddingBottom: "10px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <h1 style={{ fontFamily: "var(--font-sans)", fontSize: "1.25rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
            Ask
          </h1>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.7rem",
              fontWeight: 500,
              color: "var(--accent)",
              background: "var(--accent-soft)",
              padding: "2px 8px",
              borderRadius: "9999px",
            }}
          >
            qwen2.5:3b
          </span>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.7rem",
              fontWeight: 500,
              color: "var(--text-secondary)",
              background: "var(--bg-hover)",
              padding: "2px 8px",
              borderRadius: "9999px",
            }}
          >
            locallens
          </span>
        </div>
        {hasMessages && (
          <button
            onClick={clearChat}
            className="sk-press"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              fontFamily: "var(--font-sans)",
              fontSize: "0.8rem",
              fontWeight: 500,
              color: "var(--text-tertiary)",
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px 8px",
              borderRadius: "6px",
              transition: "color 150ms ease",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--danger)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-tertiary)"; }}
          >
            <Trash2 style={{ width: 14, height: 14 }} />
            Clear
          </button>
        )}
      </div>

      {/* Ollama offline warning */}
      {ollamaOffline && (
        <div
          style={{
            marginBottom: "12px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            borderRadius: "8px",
            padding: "10px 16px",
            fontSize: "0.85rem",
            background: "#FFFBEB",
            color: "#92400E",
            border: "1px solid #FDE68A",
            fontFamily: "var(--font-sans)",
          }}
        >
          <AlertTriangle style={{ width: 16, height: 16, color: "#D97706", flexShrink: 0 }} />
          <span>
            Ollama is not running. Start it with <code style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>ollama serve</code> to enable Ask.
          </span>
        </div>
      )}

      {/* Main content: two-column grid */}
      <div
        className="sk-ask-grid"
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: hasMessages ? "1fr" : "1fr",
          gap: "0",
          minHeight: 0,
          overflow: "hidden",
        }}
      >
        {/* We use a responsive approach: when there are messages and sources, show two columns */}
        {hasMessages ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: latestSources.length > 0 ? "3fr 2fr" : "1fr",
              gap: "16px",
              minHeight: 0,
              overflow: "hidden",
            }}
            className="sk-ask-columns"
          >
            {/* Left column: chat messages */}
            <ScrollArea style={{ minHeight: 0, paddingRight: "8px" }} ref={scrollRef}>
              <div style={{ paddingBottom: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
                {messages.map((msg, msgIdx) => {
                  const isLastAssistant = msg.role === "assistant" && msg === messages[messages.length - 1];
                  const isCurrentlyStreaming = isStreaming && isLastAssistant;

                  return (
                    <div
                      key={msg.id}
                      className="sk-msg-enter"
                      style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}
                    >
                      {msg.role === "user" ? (
                        /* User bubble */
                        <div
                          style={{
                            maxWidth: "80%",
                            padding: "10px 16px",
                            fontSize: "0.875rem",
                            background: "var(--ink)",
                            color: "var(--bg-card)",
                            fontFamily: "var(--font-sans)",
                            borderRadius: "6px",
                            borderTopRightRadius: "0",
                            lineHeight: 1.55,
                          }}
                        >
                          <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{msg.content}</p>
                        </div>
                      ) : (
                        /* Assistant bubble */
                        <div
                          style={{
                            maxWidth: "85%",
                            fontSize: "0.875rem",
                            background: "var(--bg-card)",
                            color: "var(--text-primary)",
                            fontFamily: "var(--font-sans)",
                            borderRadius: "6px",
                            borderTopLeftRadius: "0",
                            border: isCurrentlyStreaming
                              ? "1.5px solid var(--accent)"
                              : "1.5px solid var(--ink)",
                            overflow: "hidden",
                          }}
                        >
                          <div style={{ padding: "10px 14px" }}>
                            <p style={{ margin: 0, whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
                              {msg.content}
                            </p>
                            {isCurrentlyStreaming && !msg.content && (
                              <Loader2 style={{ width: 16, height: 16, color: "var(--accent)" }} className="animate-spin" />
                            )}
                            {isCurrentlyStreaming && msg.content && (
                              <span
                                style={{
                                  display: "inline-block",
                                  marginTop: "6px",
                                  fontFamily: "var(--font-mono)",
                                  fontSize: "0.65rem",
                                  color: "var(--accent)",
                                  letterSpacing: "0.03em",
                                }}
                              >
                                streaming...
                              </span>
                            )}

                            {/* Inline source citation pills */}
                            {msg.sources && msg.sources.length > 0 && (
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "8px" }}>
                                {msg.sources.map((src, i) => (
                                  <span
                                    key={i}
                                    style={{
                                      fontFamily: "var(--font-mono)",
                                      fontSize: "8px",
                                      border: "1px solid var(--accent)",
                                      padding: "1px 4px",
                                      borderRadius: "8px",
                                      color: "var(--accent)",
                                      lineHeight: 1.4,
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    {i + 1} {src.file_name}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Action bar: listen, retry, copy */}
                          {msg.content && !isCurrentlyStreaming && (
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "2px",
                                padding: "4px 10px",
                                borderTop: "1px solid var(--border)",
                                background: "transparent",
                              }}
                            >
                              {voiceAvailable.tts && (
                                <button
                                  onClick={() => playMessage(msg)}
                                  disabled={isStreaming}
                                  className="sk-press"
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    padding: "3px 6px",
                                    borderRadius: "4px",
                                    border: "none",
                                    background: getTtsState(msg.id) === "playing" ? "var(--accent-soft)" : "transparent",
                                    color: getTtsState(msg.id) === "idle" ? "var(--text-tertiary)" : "var(--accent)",
                                    fontFamily: "var(--font-mono)",
                                    fontSize: "0.65rem",
                                    fontWeight: 500,
                                    cursor: "pointer",
                                    transition: "all 150ms ease",
                                  }}
                                >
                                  {getTtsState(msg.id) === "loading" ? (
                                    <>
                                      <Loader2 style={{ width: 12, height: 12 }} className="animate-spin" />
                                      <span>synth</span>
                                    </>
                                  ) : getTtsState(msg.id) === "playing" ? (
                                    <>
                                      <Square style={{ width: 10, height: 10 }} fill="currentColor" />
                                      <span>stop</span>
                                      <span style={{ display: "inline-flex", alignItems: "flex-end", gap: "2px", marginLeft: "2px" }}>
                                        {[1, 2, 3].map((i) => (
                                          <span
                                            key={i}
                                            style={{
                                              display: "inline-block",
                                              width: "2px",
                                              borderRadius: "9999px",
                                              background: "var(--accent)",
                                              animation: `tts-bar 0.8s ease-in-out ${i * 0.15}s infinite alternate`,
                                            }}
                                          />
                                        ))}
                                      </span>
                                    </>
                                  ) : (
                                    <>
                                      <Volume2 style={{ width: 12, height: 12 }} />
                                      <span>listen</span>
                                    </>
                                  )}
                                </button>
                              )}
                              <button
                                onClick={() => retryMessage(msg)}
                                className="sk-press"
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  padding: "3px 6px",
                                  borderRadius: "4px",
                                  border: "none",
                                  background: "transparent",
                                  color: "var(--text-tertiary)",
                                  fontFamily: "var(--font-mono)",
                                  fontSize: "0.65rem",
                                  fontWeight: 500,
                                  cursor: "pointer",
                                  transition: "color 150ms ease",
                                }}
                                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-tertiary)"; }}
                              >
                                <RotateCcw style={{ width: 11, height: 11 }} />
                                <span>retry</span>
                              </button>
                              <button
                                onClick={() => copyMessage(msg)}
                                className="sk-press"
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  padding: "3px 6px",
                                  borderRadius: "4px",
                                  border: "none",
                                  background: "transparent",
                                  color: "var(--text-tertiary)",
                                  fontFamily: "var(--font-mono)",
                                  fontSize: "0.65rem",
                                  fontWeight: 500,
                                  cursor: "pointer",
                                  transition: "color 150ms ease",
                                }}
                                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-tertiary)"; }}
                              >
                                <Copy style={{ width: 11, height: 11 }} />
                                <span>copy</span>
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Skeleton bubble while streaming and assistant content is empty */}
                {isStreaming && messages.length > 0 && messages[messages.length - 1].role === "assistant" && !messages[messages.length - 1].content && (
                  <div style={{ display: "flex", justifyContent: "flex-start" }}>
                    <div
                      style={{
                        maxWidth: "80%",
                        padding: "12px 16px",
                        background: "var(--bg-card)",
                        borderRadius: "6px",
                        borderTopLeftRadius: "0",
                        border: "1.5px solid var(--accent)",
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        <div className="sk-skeleton" style={{ height: 12, width: 200 }} />
                        <div className="sk-skeleton" style={{ height: 12, width: 150 }} />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>

            {/* Right column: sources panel */}
            {latestSources.length > 0 && (
              <div
                className="sk-sources-panel"
                style={{
                  minHeight: 0,
                  display: "flex",
                  flexDirection: "column",
                  borderLeft: "1px solid var(--border)",
                  paddingLeft: "16px",
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.7rem",
                    fontWeight: 500,
                    color: "var(--text-secondary)",
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                    marginBottom: "10px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  Sources
                  <span style={{ color: "var(--text-tertiary)" }}>.</span>
                  <span style={{ color: "var(--accent)" }}>{latestSources.length}</span>
                </div>
                <ScrollArea style={{ flex: 1, minHeight: 0 }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px", paddingRight: "4px", paddingBottom: "8px" }}>
                    {latestSources.map((src, i) => {
                      const isTop = i === 0;
                      return (
                        <div
                          key={i}
                          style={{
                            padding: "10px 12px",
                            borderRadius: "8px",
                            background: isTop ? "var(--accent-soft)" : "var(--bg-page)",
                            border: isTop ? "1.5px solid var(--accent)" : "1px solid var(--border)",
                            transition: "border-color 150ms ease",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginBottom: "6px" }}>
                            <span
                              style={{
                                fontFamily: "var(--font-mono)",
                                fontSize: "0.65rem",
                                fontWeight: 600,
                                color: isTop ? "var(--accent)" : "var(--text-tertiary)",
                                minWidth: "14px",
                              }}
                            >
                              {i + 1}
                            </span>
                            <span
                              style={{
                                fontFamily: "var(--font-sans)",
                                fontSize: "0.8rem",
                                fontWeight: 600,
                                color: "var(--text-primary)",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {src.file_name}
                            </span>
                          </div>
                          {src.chunk_preview ? (
                            <p
                              style={{
                                margin: 0,
                                fontFamily: "var(--font-sans)",
                                fontSize: "0.75rem",
                                color: "var(--text-tertiary)",
                                lineHeight: 1.45,
                                display: "-webkit-box",
                                WebkitLineClamp: 3,
                                WebkitBoxOrient: "vertical",
                                overflow: "hidden",
                              }}
                            >
                              {src.chunk_preview}
                            </p>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                              <div style={{ height: 8, width: "90%", borderRadius: 4, background: "var(--bg-hover)" }} />
                              <div style={{ height: 8, width: "70%", borderRadius: 4, background: "var(--bg-hover)" }} />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </div>
            )}
          </div>
        ) : (
          /* Empty state */
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "24px", padding: "64px 0" }}>
            {voiceAvailable.stt && (
              <div
                className="sk-mic-hint-pulse"
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: "9999px",
                  background: "var(--accent-soft)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Mic style={{ width: 24, height: 24, color: "var(--accent)" }} />
              </div>
            )}
            <div style={{ textAlign: "center" }}>
              <p style={{ fontSize: "1.1rem", color: "var(--text-primary)", fontFamily: "var(--font-sans)", fontWeight: 600, margin: "0 0 4px 0" }}>
                Ask a question about your files
              </p>
              <p style={{ fontSize: "0.85rem", color: "var(--text-tertiary)", fontFamily: "var(--font-sans)", margin: 0 }}>
                Try asking...
              </p>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", width: "100%", maxWidth: "520px", padding: "0 8px" }}>
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="sk-press"
                  onClick={() => askQuestion(q)}
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: "0.85rem",
                    color: "var(--text-primary)",
                    background: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    boxShadow: "var(--shadow-xs)",
                    padding: "12px 16px",
                    textAlign: "left",
                    cursor: "pointer",
                    transition: "border-color 150ms ease, box-shadow 150ms ease, background 150ms ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "var(--accent)";
                    e.currentTarget.style.boxShadow = "var(--shadow-sm)";
                    e.currentTarget.style.background = "rgba(198,123,60,0.04)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--border)";
                    e.currentTarget.style.boxShadow = "var(--shadow-xs)";
                    e.currentTarget.style.background = "var(--bg-card)";
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div
          style={{
            marginTop: "8px",
            marginBottom: "4px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            borderRadius: "8px",
            padding: "10px 16px",
            fontSize: "0.85rem",
            background: "#FEF2F2",
            color: "var(--danger)",
            border: "1px solid #FECACA",
            fontFamily: "var(--font-sans)",
          }}
        >
          <AlertCircle style={{ width: 16, height: 16, flexShrink: 0 }} />
          <span>{error}</span>
          {error.includes("No files indexed") && (
            <Link
              to="/index"
              style={{ marginLeft: "auto", textDecoration: "underline", color: "var(--accent)" }}
            >
              Index files
            </Link>
          )}
        </div>
      )}

      {/* Input bar at bottom: pill-shaped, spanning full width */}
      <div
        style={{
          marginTop: "auto",
          paddingTop: "12px",
          paddingBottom: "4px",
          position: "sticky",
          bottom: 0,
          background: "var(--bg-page)",
          zIndex: 10,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0",
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: "9999px",
            padding: "4px 4px 4px 16px",
            boxShadow: "var(--shadow-sm)",
            transition: "border-color 150ms ease, box-shadow 150ms ease",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--accent)";
            e.currentTarget.style.boxShadow = "0 0 0 3px rgba(198, 123, 60, 0.08)";
          }}
          onBlur={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget)) {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.boxShadow = "var(--shadow-sm)";
            }
          }}
        >
          <Search style={{ width: 16, height: 16, color: "var(--text-tertiary)", flexShrink: 0 }} />
          <input
            type="text"
            placeholder={isRecording ? "Listening..." : isTranscribing ? "Transcribing..." : "ask another..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
                e.preventDefault();
                askQuestion(input);
              }
            }}
            disabled={isStreaming || isRecording || isTranscribing}
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontFamily: "var(--font-sans)",
              fontSize: "0.9rem",
              color: "var(--text-primary)",
              padding: "8px 12px",
              minWidth: 0,
            }}
          />
          <div style={{ display: "flex", alignItems: "center", gap: "4px", flexShrink: 0 }}>
            {voiceAvailable.stt && (
              <button
                type="button"
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isStreaming || isTranscribing}
                title={isRecording ? "Stop recording" : "Record a question"}
                aria-label="Record voice question"
                className={`sk-press ${isRecording ? "sk-voice-orb-pulse" : ""}`}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "9999px",
                  border: "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: isStreaming || isTranscribing ? "not-allowed" : "pointer",
                  background: isRecording ? "var(--accent)" : "var(--accent-soft)",
                  color: isRecording ? "var(--text-on-accent)" : "var(--accent)",
                  transition: "all 200ms ease",
                  opacity: isStreaming || isTranscribing ? 0.5 : 1,
                }}
              >
                {isTranscribing ? (
                  <Loader2 style={{ width: 16, height: 16 }} className="animate-spin" />
                ) : (
                  <Mic style={{ width: 16, height: 16 }} strokeWidth={2} />
                )}
              </button>
            )}
            <button
              type="button"
              onClick={() => askQuestion(input)}
              disabled={isStreaming || isRecording || isTranscribing || inputEmpty}
              className="sk-press"
              style={{
                width: 36,
                height: 36,
                borderRadius: "9999px",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: inputEmpty ? "not-allowed" : "pointer",
                background: inputEmpty ? "var(--bg-hover)" : "var(--accent)",
                color: inputEmpty ? "var(--text-tertiary)" : "var(--text-on-accent)",
                transition: "all 200ms ease",
                opacity: inputEmpty || isStreaming ? 0.6 : 1,
              }}
            >
              <Send style={{ width: 16, height: 16 }} />
            </button>
          </div>
        </div>
        <p
          style={{
            marginTop: "4px",
            paddingBottom: "4px",
            textAlign: "right",
            fontSize: "0.65rem",
            color: "var(--text-tertiary)",
            fontFamily: "var(--font-sans)",
          }}
        >
          {voiceAvailable.stt ? "Press Enter to send, tap the mic to speak" : "Press Enter to send"}
        </p>
      </div>

      {/* Responsive styles injected via style tag */}
      <style>{`
        .sk-ask-columns {
          min-height: 0;
        }
        @media (max-width: 768px) {
          .sk-ask-columns {
            grid-template-columns: 1fr !important;
          }
          .sk-sources-panel {
            border-left: none !important;
            border-top: 1px solid var(--border);
            padding-left: 0 !important;
            padding-top: 12px;
            max-height: 200px;
          }
        }
        @media (max-width: 520px) {
          .sk-ask-page {
            padding: 0 0.5rem !important;
          }
        }
        .sk-voice-orb-pulse {
          animation: sk-voice-orb-pulse-kf 1.6s ease-in-out infinite;
        }
        @keyframes sk-voice-orb-pulse-kf {
          0%, 100% { box-shadow: 0 0 0 0 rgba(198,123,60,0.3); }
          50% { box-shadow: 0 0 0 8px rgba(198,123,60,0.08); }
        }
      `}</style>
    </div>
  );
}
