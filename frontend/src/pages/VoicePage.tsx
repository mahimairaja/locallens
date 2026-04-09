import { useState, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { motion } from "framer-motion";

interface VoiceEntry {
  role: "user" | "assistant";
  text: string;
  sources?: { file_name: string }[];
}

export default function VoicePage() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState<VoiceEntry[]>([]);
  const [stateText, setStateText] = useState("Press and hold to speak");
  const [voiceAvailable, setVoiceAvailable] = useState<boolean | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    // Check voice availability
    fetch("/api/voice/status")
      .then((r) => r.json())
      .then((data) => setVoiceAvailable(data.stt_available || data.tts_available))
      .catch(() => setVoiceAvailable(false));

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const drawWaveform = () => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animFrameRef.current = requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(dataArray);

      ctx.fillStyle = "rgba(15, 23, 42, 0.3)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.lineWidth = 2;
      ctx.strokeStyle = isRecording ? "#06b6d4" : "#475569";
      ctx.beginPath();

      const sliceWidth = canvas.width / bufferLength;
      let x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }

      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
    };

    draw();
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Audio visualizer
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      analyserRef.current = analyser;

      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        await processAudio(blob);
      };

      recorder.start();
      setIsRecording(true);
      setStateText("Listening...");
      drawWaveform();
    } catch {
      setStateText("Microphone access denied");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    setStateText("Thinking...");
  };

  const processAudio = async (blob: Blob) => {
    setIsProcessing(true);
    try {
      const result = await api.voiceConversation(blob);
      setTranscript((prev) => [
        ...prev,
        { role: "user", text: result.transcription },
        {
          role: "assistant",
          text: result.response_text,
          sources: result.sources as { file_name: string }[] | undefined,
        },
      ]);

      // Play response audio if available
      if (result.audio_url) {
        setStateText("Speaking...");
        const audio = new Audio(result.audio_url);
        audio.onended = () => setStateText("Press and hold to speak");
        await audio.play();
      } else {
        setStateText("Press and hold to speak");
      }
    } catch {
      setStateText("Error processing audio. Try again.");
      setTimeout(() => setStateText("Press and hold to speak"), 3000);
    } finally {
      setIsProcessing(false);
    }
  };

  if (voiceAvailable === false) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Card className="max-w-md">
          <CardContent className="space-y-3 p-6 text-center">
            <MicOff className="mx-auto h-10 w-10 text-muted-foreground" />
            <p className="text-lg font-medium">Voice not available</p>
            <p className="text-sm text-muted-foreground">
              Voice dependencies are not installed. Install them with:
            </p>
            <code className="block rounded bg-muted px-3 py-2 text-sm">
              pip install "locallens[voice]"
            </code>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center space-y-8 py-8">
      {/* Waveform */}
      <canvas
        ref={canvasRef}
        width={500}
        height={80}
        className="w-full max-w-md rounded-lg"
      />

      {/* Push to Talk Button */}
      <motion.button
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onTouchStart={startRecording}
        onTouchEnd={stopRecording}
        disabled={isProcessing}
        className={`flex h-28 w-28 items-center justify-center rounded-full border-4 transition-colors ${
          isRecording
            ? "border-red-500 bg-red-500/20"
            : isProcessing
            ? "border-muted bg-muted/20"
            : "border-primary bg-primary/10 hover:bg-primary/20"
        }`}
        animate={isRecording ? { scale: [1, 1.05, 1] } : {}}
        transition={isRecording ? { repeat: Infinity, duration: 1 } : {}}
      >
        {isProcessing ? (
          <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
        ) : (
          <Mic
            className={`h-10 w-10 ${
              isRecording ? "text-red-500" : "text-primary"
            }`}
          />
        )}
      </motion.button>

      {/* State text */}
      <p className="text-sm text-muted-foreground">{stateText}</p>

      {/* Transcript */}
      {transcript.length > 0 && (
        <Card className="w-full">
          <CardContent className="space-y-4 p-6">
            {transcript.map((entry, i) => (
              <div key={i}>
                <p className="text-xs font-medium text-muted-foreground uppercase mb-1">
                  {entry.role === "user" ? "You" : "LocalLens"}
                </p>
                <p className="text-sm">{entry.text}</p>
                {entry.sources && entry.sources.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {entry.sources.map((src, j) => (
                      <Badge key={j} variant="secondary" className="text-xs">
                        {src.file_name}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
