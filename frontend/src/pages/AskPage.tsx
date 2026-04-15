import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Trash2, Loader2, AlertCircle, Mic, Volume2, Square, VolumeX, AlertTriangle } from "lucide-react";
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

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col">
      {/* Header with Clear */}
      <div className="mb-3 flex items-center justify-end">
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearChat}>
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
          <div className="flex h-full flex-col items-center justify-center space-y-8 py-16">
            <p
              className="text-lg"
              style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
            >
              Ask a question about your indexed files
            </p>
            <div className="grid w-full grid-cols-1 gap-3 px-2 sm:grid-cols-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <div
                  key={q}
                  className="sk-postit"
                  onClick={() => askQuestion(q)}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-sans)",
                      fontSize: "0.9rem",
                      color: "var(--text-primary)",
                    }}
                  >
                    {q}
                  </span>
                </div>
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
                {msg.role === "user" ? (
                  <div
                    className="max-w-[80%] px-4 py-3 text-sm"
                    style={{
                      background: "var(--accent-soft)",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-sans)",
                      borderRadius: "var(--radius-lg) var(--radius-lg) 4px var(--radius-lg)",
                    }}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                ) : (
                  <div
                    className="max-w-[80%] text-sm"
                    style={{
                      background: "var(--bg-card)",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-sans)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px",
                      boxShadow: "var(--shadow-xs)",
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
                      {msg.sources && msg.sources.length > 0 && (
                        <div
                          className="mt-3 flex flex-wrap gap-1.5 pt-2.5"
                          style={{ borderTop: "1px solid var(--border)" }}
                        >
                          {msg.sources.map((src, i) => (
                            <span key={i} className="sk-source-tag">
                              {src.file_name}
                            </span>
                          ))}
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
                          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-all"
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

      {/* Input */}
      <div
        className="mt-4 flex items-center gap-2 pt-4"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <Input
          placeholder={isRecording ? "Listening…" : isTranscribing ? "Transcribing…" : "Ask a question..."}
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
        />
        {voiceAvailable.stt && (
          <button
            type="button"
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isStreaming || isTranscribing}
            title={isRecording ? "Stop recording" : "Record a question"}
            aria-label="Record voice question"
            className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] transition-all disabled:opacity-50"
            style={{
              background: isRecording ? "var(--accent)" : "var(--bg-card)",
              color: isRecording ? "var(--text-on-accent)" : "var(--text-secondary)",
              border: `1px solid ${isRecording ? "var(--accent)" : "var(--border)"}`,
              boxShadow: "var(--shadow-xs)",
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
          disabled={isStreaming || isRecording || isTranscribing || !input.trim()}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <p
        className="mt-1 text-right text-[0.7rem]"
        style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
      >
        {voiceAvailable.stt ? "Press Enter to send · tap the mic to speak" : "Press Enter to send"}
      </p>
    </div>
  );
}
