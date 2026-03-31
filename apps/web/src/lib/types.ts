export type SessionStatus = "idle" | "listening" | "processing" | "stopped";

export interface Utterance {
  id: string;
  speaker: string;
  start_ms: number;
  end_ms: number;
  source_lang: "ko" | "en";
  source_text: string;
  translated_text: string;
  status: "partial" | "final";
}

export interface SessionSnapshot {
  session_id: string | null;
  status: SessionStatus;
  started_at: string | null;
  updated_at: string | null;
  audio_level: number;
  active_utterance_id: string | null;
  transcription_provider: string;
  translation_provider: string;
  hotwords: string[];
  utterances: Utterance[];
  last_error: string | null;
}

export interface LiveEvent {
  type: string;
  payload: SessionSnapshot;
}

export interface SampleFileInfo {
  name: string;
  size_bytes: number;
}
