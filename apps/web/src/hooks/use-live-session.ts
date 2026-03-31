import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AudioStreamer } from "../lib/audio-streamer";
import type { LiveEvent, SessionSnapshot } from "../lib/types";

const EMPTY_SNAPSHOT: SessionSnapshot = {
  session_id: null,
  status: "idle",
  started_at: null,
  updated_at: null,
  audio_level: 0,
  active_utterance_id: null,
  transcription_provider: "mock",
  translation_provider: "noop",
  hotwords: [],
  utterances: [],
  last_error: null,
};

type StartOptions = {
  hotwords: string[];
};

export function useLiveSession() {
  const [snapshot, setSnapshot] = useState<SessionSnapshot>(EMPTY_SNAPSHOT);
  const [isConnecting, setIsConnecting] = useState(false);
  const [clientLevel, setClientLevel] = useState(0);

  const audioRef = useRef<AudioStreamer | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const apiBaseUrl = useMemo(() => {
    return (
      import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
      "http://127.0.0.1:8000"
    );
  }, []);

  const wsUrl = useMemo(() => {
    return apiBaseUrl.replace(/^http/, "ws") + "/ws/live";
  }, [apiBaseUrl]);

  const fetchSnapshot = useCallback(async () => {
    const response = await fetch(`${apiBaseUrl}/api/session/current`);
    const data = (await response.json()) as SessionSnapshot;
    setSnapshot(data);
  }, [apiBaseUrl]);

  useEffect(() => {
    void fetchSnapshot();
  }, [fetchSnapshot]);

  const stopSession = useCallback(async () => {
    socketRef.current?.close();
    socketRef.current = null;

    if (audioRef.current) {
      await audioRef.current.stop();
      audioRef.current = null;
    }

    await fetch(`${apiBaseUrl}/api/session/stop`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    await fetchSnapshot();
  }, [apiBaseUrl, fetchSnapshot]);

  const startSession = useCallback(
    async ({ hotwords }: StartOptions) => {
      setIsConnecting(true);

      try {
        await fetch(`${apiBaseUrl}/api/session/start`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ hotwords }),
        });

        const socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onmessage = (event) => {
          const message = JSON.parse(event.data) as LiveEvent;
          setSnapshot(message.payload);
        };

        socket.onerror = () => {
          setSnapshot((current) => ({
            ...current,
            last_error: "WebSocket connection failed.",
          }));
        };

        await new Promise<void>((resolve, reject) => {
          socket.onopen = () => resolve();
          socket.onclose = () => reject(new Error("WebSocket closed early."));
        });

        const audio = new AudioStreamer();
        audioRef.current = audio;

        const sampleRate = await audio.start({
          onChunk: (chunk) => {
            if (socketRef.current?.readyState !== WebSocket.OPEN) {
              return;
            }
            socketRef.current.send(chunk.buffer);
          },
          onLevel: (level) => setClientLevel(level),
        });

        socket.send(
          JSON.stringify({
            type: "audio.config",
            payload: { sampleRate },
          }),
        );

        await fetchSnapshot();
      } finally {
        setIsConnecting(false);
      }
    },
    [apiBaseUrl, fetchSnapshot, wsUrl],
  );

  return {
    snapshot,
    isConnecting,
    clientLevel,
    startSession,
    stopSession,
  };
}
