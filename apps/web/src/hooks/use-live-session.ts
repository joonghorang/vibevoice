import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AudioStreamer } from "../lib/audio-streamer";
import type { LiveEvent, SampleFileInfo, SessionSnapshot } from "../lib/types";

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
  const [isProcessingFile, setIsProcessingFile] = useState(false);
  const [clientLevel, setClientLevel] = useState(0);
  const [sampleFiles, setSampleFiles] = useState<SampleFileInfo[]>([]);

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
    await ensureOk(response);
    const data = (await response.json()) as SessionSnapshot;
    setSnapshot(data);
  }, [apiBaseUrl]);

  const fetchSamples = useCallback(async () => {
    const response = await fetch(`${apiBaseUrl}/api/samples`);
    await ensureOk(response);
    const data = (await response.json()) as SampleFileInfo[];
    setSampleFiles(data);
  }, [apiBaseUrl]);

  useEffect(() => {
    void fetchSnapshot();
    void fetchSamples();
  }, [fetchSamples, fetchSnapshot]);

  const stopRealtimeResources = useCallback(async () => {
    socketRef.current?.close();
    socketRef.current = null;

    if (audioRef.current) {
      await audioRef.current.stop();
      audioRef.current = null;
    }
  }, []);

  const stopSession = useCallback(async () => {
    await stopRealtimeResources();

    await fetch(`${apiBaseUrl}/api/session/stop`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    await fetchSnapshot();
  }, [apiBaseUrl, fetchSnapshot, stopRealtimeResources]);

  const startSession = useCallback(
    async ({ hotwords }: StartOptions) => {
      setIsConnecting(true);

      try {
        await stopRealtimeResources();

        const startResponse = await fetch(`${apiBaseUrl}/api/session/start`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ hotwords }),
        });
        await ensureOk(startResponse);

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
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to start session.";
        setSnapshot((current) => ({
          ...current,
          last_error: message,
        }));
      } finally {
        setIsConnecting(false);
      }
    },
    [apiBaseUrl, fetchSnapshot, stopRealtimeResources, wsUrl],
  );

  const processSample = useCallback(
    async (sampleName: string, hotwords: string[]) => {
      setIsProcessingFile(true);

      try {
        await stopRealtimeResources();

        const response = await fetch(`${apiBaseUrl}/api/session/process-sample`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            sample_name: sampleName,
            hotwords,
          }),
        });
        await ensureOk(response);
        const data = (await response.json()) as SessionSnapshot;
        setSnapshot(data);
        await fetchSnapshot();
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to process sample.";
        setSnapshot((current) => ({
          ...current,
          last_error: message,
        }));
      } finally {
        setIsProcessingFile(false);
      }
    },
    [apiBaseUrl, fetchSnapshot, stopRealtimeResources],
  );

  const uploadAudioFile = useCallback(
    async (file: File, hotwords: string[]) => {
      setIsProcessingFile(true);

      try {
        await stopRealtimeResources();

        const formData = new FormData();
        formData.append("file", file);
        formData.append("hotwords", hotwords.join(","));

        const response = await fetch(`${apiBaseUrl}/api/session/upload`, {
          method: "POST",
          body: formData,
        });
        await ensureOk(response);
        const data = (await response.json()) as SessionSnapshot;
        setSnapshot(data);
        await fetchSnapshot();
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to upload audio.";
        setSnapshot((current) => ({
          ...current,
          last_error: message,
        }));
      } finally {
        setIsProcessingFile(false);
      }
    },
    [apiBaseUrl, fetchSnapshot, stopRealtimeResources],
  );

  return {
    snapshot,
    isConnecting,
    isProcessingFile,
    clientLevel,
    sampleFiles,
    startSession,
    stopSession,
    processSample,
    uploadAudioFile,
  };
}

async function ensureOk(response: Response): Promise<void> {
  if (response.ok) {
    return;
  }

  let message = `Request failed with status ${response.status}`;
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) {
      message = payload.detail;
    }
  } catch {
    // Ignore JSON parse failures and keep the fallback message.
  }

  throw new Error(message);
}
