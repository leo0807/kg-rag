"use client";

import { Mic, MicOff } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { VoiceWaveform } from "./VoiceWaveform";

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

/** Mic button with Web Speech API; shows waveform while recording. */
export function VoiceInputButton({ onTranscript, disabled }: Props) {
  const [recording, setRecording] = useState(false);
  const [supported] = useState(() => typeof window !== "undefined" && "webkitSpeechRecognition" in window);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setRecording(false);
  }, []);

  useEffect(() => () => { recognitionRef.current?.stop(); }, []);

  const toggle = useCallback(() => {
    if (!supported) return;
    if (recording) { stop(); return; }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = "zh-CN";
    rec.continuous = false;
    rec.interimResults = false;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onresult = (e: any) => {
      const transcript = e.results[0][0].transcript;
      onTranscript(transcript);
    };
    rec.onerror = () => setRecording(false);
    rec.onend = () => setRecording(false);

    recognitionRef.current = rec;
    rec.start();
    setRecording(true);
  }, [supported, recording, stop, onTranscript]);

  if (!supported) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      title={recording ? "点击停止录音" : "语音输入"}
      className={`flex items-center gap-1.5 p-2 rounded-lg transition-colors ${
        recording
          ? "text-red-400 bg-red-950/40 hover:bg-red-900/40"
          : "text-gray-500 hover:text-gray-300 hover:bg-gray-800"
      } disabled:opacity-40`}
    >
      {recording ? (
        <>
          <VoiceWaveform active={recording} color="#f87171" />
          <MicOff size={15} />
        </>
      ) : (
        <Mic size={15} />
      )}
    </button>
  );
}
