import type { SessionSnapshot } from "../lib/types";

type HeaderBarProps = {
  snapshot: SessionSnapshot;
  clientLevel: number;
  isConnecting: boolean;
  hotwordsText: string;
  onHotwordsChange: (value: string) => void;
  onStart: () => void;
  onStop: () => void;
};

export function HeaderBar(props: HeaderBarProps) {
  const {
    snapshot,
    clientLevel,
    isConnecting,
    hotwordsText,
    onHotwordsChange,
    onStart,
    onStop,
  } = props;

  const isRunning =
    snapshot.status === "listening" || snapshot.status === "processing";

  return (
    <header className="topbar">
      <div className="brand-block">
        <p className="eyebrow">Classroom Captioning</p>
        <h1>VibeVoice Classroom</h1>
        <p className="subcopy">
          Left panel stays in the source language, right panel follows with the
          opposite translation.
        </p>
      </div>

      <div className="controls">
        <label className="hotword-field">
          <span>Hotwords</span>
          <input
            value={hotwordsText}
            onChange={(event) => onHotwordsChange(event.target.value)}
            placeholder="교수명, 과목명, 전공 용어"
          />
        </label>

        <div className="status-pill-row">
          <span className={`status-pill status-${snapshot.status}`}>
            {snapshot.status}
          </span>
          <span className="status-pill muted">
            mic {Math.round(clientLevel * 100)}%
          </span>
          <span className="status-pill muted">
            ASR {snapshot.transcription_provider}
          </span>
          <span className="status-pill muted">
            Translate {snapshot.translation_provider}
          </span>
        </div>

        <div className="button-row">
          <button
            className="primary-button"
            onClick={onStart}
            disabled={isRunning || isConnecting}
          >
            {isConnecting ? "Starting..." : "Start Session"}
          </button>
          <button
            className="secondary-button"
            onClick={onStop}
            disabled={!isRunning}
          >
            Stop
          </button>
        </div>
      </div>
    </header>
  );
}
