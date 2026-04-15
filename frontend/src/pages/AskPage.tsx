import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Trash2, Loader2, AlertCircle, Mic, Volume2, Square, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
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
        setError("Didn't catch that — try speaking again.");
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

  const inputEmpty = !input.trim();

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col">
      {/* Header with Clear */}
      <div className="mb-3 flex items-center justify-end">
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearChat} className="sk-press">
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Clear Chat
          </Button>
        )}
      </div>

      {/* Ollama offline warning */}
      {ollamaOffline && (
        <div
          className="mb-3 flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm"
          style={{
            background: "#FFFBEB",
            color: "#92400E",
            border: "1px solid #FDE68A",
            fontFamily: "var(--font-sans)",
          }}
        >
          <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: "#D97706" }} />
          <span>
            Ollama is not running. Start it with <code style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>ollama serve</code> to enable Ask.
          </span>
        </div>
      )}

      {/* Chat area */}
      <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
        {messages.length === 0 ? (
          /* ── Step 15: Empty state ── */
          <div className="flex h-full flex-col items-center justify-center space-y-6 py-16">
            {/* Mic icon hint with pulse */}
            {voiceAvailable.stt && (
              <div
                className="sk-mic-hint-pulse flex h-14 w-14 items-center justify-center rounded-full"
                style={{ background: "var(--accent-soft)" }}
              >
                <Mic className="h-6 w-6" style={{ color: "var(--accent)" }} />
              </div>
            )}
            <div className="space-y-1 text-center">
              <p
                className="text-lg"
                style={{ color: "var(--text-primary)", fontFamily: "var(--font-sans)", fontWeight: 600 }}
              >
                Ask a question about your files
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
              >
                Try asking...
              </p>
            </div>
            <div className="grid w-full grid-cols-1 gap-3 px-2 sm:grid-cols-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="sk-press rounded-xl px-4 py-3 text-left text-sm"
                  onClick={() => askQuestion(q)}
                  style={{
                    fontFamily: "var(--font-sans)",
                    color: "var(--text-primary)",
                    background: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    boxShadow: "var(--shadow-xs)",
                    transition: "border-color 150ms ease, box-shadow 150ms ease, background 150ms ease",
                    cursor: "pointer",
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
        ) : (
          /* ── Step 16: Chat messages ── */
          <div className="space-y-4 pb-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`sk-msg-enter flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "user" ? (
                  /* User bubble: copper bg, white text, sharp bottom-right */
                  <div
                    className="max-w-[80%] px-4 py-3 text-sm"
                    style={{
                      background: "#C67B3C",
                      color: "#FFFFFF",
                      fontFamily: "var(--font-sans)",
                      borderRadius: "16px 16px 4px 16px",
                    }}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                ) : (
                  /* Assistant bubble: white bg, shadow, sharp bottom-left */
                  <div
                    className="max-w-[80%] text-sm"
                    style={{
                      background: "#FFFFFF",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-sans)",
                      borderRadius: "16px 16px 16px 4px",
                      boxShadow: "0 1px 4px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04)",
                      overflow: "hidden",
                    }}
                  >
                    <div className="px-4 py-3">
                      <p className="whitespace-pre-wrap" style={{ lineHeight: 1.55 }}>
                        {msg.content}
                      </p>
                      {isStreaming && msg === messages[messages.length - 1] && !msg.content && (
                        <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--accent)" }} />
                      )}

                      {/* Collapsible sources */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div
                          className="mt-3 pt-2.5"
                          style={{ borderTop: "1px solid var(--border)" }}
                        >
                          <button
                            type="button"
                            className="sk-press flex items-center gap-1.5 text-xs"
                            style={{
                              color: "var(--accent)",
                              fontFamily: "var(--font-sans)",
                              fontWeight: 500,
                              cursor: "pointer",
                              background: "none",
                              border: "none",
                              padding: 0,
                            }}
                            onClick={() => toggleSources(msg.id)}
                          >
                            {expandedSources[msg.id] ? (
                              <ChevronDown className="h-3.5 w-3.5" />
                            ) : (
                              <ChevronRight className="h-3.5 w-3.5" />
                            )}
                            {msg.sources.length} source{msg.sources.length !== 1 ? "s" : ""}
                          </button>
                          {expandedSources[msg.id] && (
                            <div className="mt-2 space-y-1.5">
                              {msg.sources.map((src, i) => (
                                <div
                                  key={i}
                                  className="rounded-lg px-3 py-2"
                                  style={{
                                    background: "var(--bg-page)",
                                    border: "1px solid var(--border)",
                                    borderRadius: "8px",
                                  }}
                                >
                                  <p
                                    className="text-xs"
                                    style={{
                                      fontWeight: 600,
                                      color: "var(--text-primary)",
                                      fontFamily: "var(--font-sans)",
                                    }}
                                  >
                                    {src.file_name}
                                  </p>
                                  {src.chunk_preview && (
                                    <p
                                      className="mt-1 line-clamp-2 text-xs"
                                      style={{
                                        color: "var(--text-tertiary)",
                                        fontFamily: "var(--font-sans)",
                                        lineHeight: 1.45,
                                      }}
                                    >
                                      {src.chunk_preview}
                                    </p>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* TTS inline action bar */}
                    {voiceAvailable.tts && msg.content && !isStreaming && (
                      <div
                        className="flex items-center gap-2 px-4 py-2"
                        style={{
                          borderTop: "1px solid var(--border)",
                          background: getTtsState(msg.id) === "playing"
                            ? "var(--accent-soft)"
                            : "transparent",
                          transition: "background 0.2s ease",
                        }}
                      >
                        <button
                          onClick={() => playMessage(msg)}
                          disabled={isStreaming}
                          className="sk-press flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-all"
                          style={{
                            color: getTtsState(msg.id) === "idle"
                              ? "var(--text-tertiary)"
                              : "var(--accent)",
                            fontFamily: "var(--font-sans)",
                            fontWeight: 500,
                          }}
                        >
                          {getTtsState(msg.id) === "loading" ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              <span>Synthesizing...</span>
                            </>
                          ) : getTtsState(msg.id) === "playing" ? (
                            <>
                              <Square className="h-3 w-3" fill="currentColor" />
                              <span>Stop</span>
                              {/* Animated audio bars */}
                              <span className="ml-1 flex items-end gap-[2px]">
                                {[1, 2, 3].map((i) => (
                                  <span
                                    key={i}
                                    className="inline-block w-[2px] rounded-full"
                                    style={{
                                      background: "var(--accent)",
                                      animation: `tts-bar 0.8s ease-in-out ${i * 0.15}s infinite alternate`,
                                    }}
                                  />
                                ))}
                              </span>
                            </>
                          ) : (
                            <>
                              <Volume2 className="h-3.5 w-3.5" />
                              <span>Listen</span>
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Skeleton bubble while streaming and assistant content is empty */}
            {isStreaming && messages.length > 0 && messages[messages.length - 1].role === "assistant" && !messages[messages.length - 1].content && (
              <div className="flex justify-start">
                <div
                  className="max-w-[80%] px-4 py-3"
                  style={{
                    background: "#FFFFFF",
                    borderRadius: "16px 16px 16px 4px",
                    boxShadow: "0 1px 4px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04)",
                  }}
                >
                  <div className="space-y-2">
                    <div className="sk-skeleton h-3" style={{ width: "200px" }} />
                    <div className="sk-skeleton h-3" style={{ width: "150px" }} />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </ScrollArea>

      {/* Error Banner */}
      {error && (
        <div
          className="mt-3 mb-1 flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm"
          style={{
            background: "#FEF2F2",
            color: "var(--danger)",
            border: "1px solid #FECACA",
            fontFamily: "var(--font-sans)",
          }}
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
          {error.includes("No files indexed") && (
            <Link
              to="/index"
              className="ml-auto underline"
              style={{ color: "var(--accent)" }}
            >
              Index files
            </Link>
          )}
        </div>
      )}

      {/* ── Step 17: Sticky input area ── */}
      <div
        className="mt-auto flex items-center gap-2 pt-4 pb-1"
        style={{
          position: "sticky",
          bottom: 0,
          background: "var(--bg-page)",
          boxShadow: "0 -4px 12px rgba(0,0,0,0.04)",
          borderRadius: "0",
          zIndex: 10,
        }}
      >
        <Input
          placeholder={isRecording ? "Listening..." : isTranscribing ? "Transcribing..." : "Ask a question..."}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
              e.preventDefault();
              askQuestion(input);
            }
          }}
          disabled={isStreaming || isRecording || isTranscribing}
          className="flex-1"
          style={{ borderRadius: "8px" }}
        />
        {voiceAvailable.stt && (
          <button
            type="button"
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isStreaming || isTranscribing}
            title={isRecording ? "Stop recording" : "Record a question"}
            aria-label="Record voice question"
            className={`sk-press flex h-9 w-9 items-center justify-center rounded-lg transition-all disabled:opacity-50 ${isRecording ? "sk-recording-pulse" : ""}`}
            style={{
              background: isRecording ? "#C67B3C" : "var(--bg-card)",
              color: isRecording ? "#FFFFFF" : "#C67B3C",
              border: `1px solid ${isRecording ? "#C67B3C" : "var(--border)"}`,
              boxShadow: "var(--shadow-xs)",
              borderRadius: "8px",
            }}
          >
            {isTranscribing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Mic className="h-4 w-4" strokeWidth={2} />
            )}
          </button>
        )}
        <Button
          onClick={() => askQuestion(input)}
          disabled={isStreaming || isRecording || isTranscribing || inputEmpty}
          className="sk-press"
          style={{
            background: inputEmpty ? "var(--bg-hover)" : "#C67B3C",
            color: inputEmpty ? "var(--text-tertiary)" : "#FFFFFF",
            border: "none",
            borderRadius: "8px",
            opacity: inputEmpty ? 0.6 : 1,
            cursor: inputEmpty ? "not-allowed" : "pointer",
          }}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <p
        className="mt-1 pb-2 text-right text-[0.7rem]"
        style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
      >
        {voiceAvailable.stt ? "Press Enter to send, tap the mic to speak" : "Press Enter to send"}
      </p>
    </div>
  );
}
