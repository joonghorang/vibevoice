import { useEffect, useMemo, useRef } from "react";
import type { Utterance } from "../lib/types";

type SubtitlePaneProps = {
  title: string;
  mode: "source" | "translation";
  utterances: Utterance[];
  activeUtteranceId: string | null;
  autoFollow: boolean;
  onPauseAutoFollow: () => void;
};

export function SubtitlePane(props: SubtitlePaneProps) {
  const {
    title,
    mode,
    utterances,
    activeUtteranceId,
    autoFollow,
    onPauseAutoFollow,
  } = props;

  const containerRef = useRef<HTMLDivElement | null>(null);
  const activeRowRef = useRef<HTMLDivElement | null>(null);

  const rows = useMemo(() => utterances.slice(-80), [utterances]);

  useEffect(() => {
    if (!autoFollow || !activeRowRef.current) {
      return;
    }

    activeRowRef.current.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, [activeUtteranceId, autoFollow, rows.length]);

  return (
    <section className="pane">
      <div className="pane-header">
        <div>
          <p className="pane-eyebrow">{mode === "source" ? "Original" : "Translated"}</p>
          <h2>{title}</h2>
        </div>
        <span className="pane-count">{rows.length} lines</span>
      </div>

      <div
        ref={containerRef}
        className="pane-scroll"
        onWheel={() => {
          if (autoFollow) {
            onPauseAutoFollow();
          }
        }}
      >
        {rows.length === 0 ? (
          <div className="empty-state">
            <p>Session has not started yet.</p>
            <span>Start the microphone stream to begin live captions.</span>
          </div>
        ) : (
          rows.map((utterance) => {
            const isActive = utterance.id === activeUtteranceId;
            const text =
              mode === "source"
                ? utterance.source_text
                : utterance.translated_text || "Translating...";

            return (
              <div
                key={`${mode}-${utterance.id}`}
                ref={isActive ? activeRowRef : null}
                className={`utterance-row ${isActive ? "active" : ""}`}
              >
                <div className="utterance-meta">
                  <span>{utterance.speaker}</span>
                  <span>{formatMs(utterance.start_ms)}</span>
                  <span className={`badge badge-${utterance.status}`}>
                    {utterance.status}
                  </span>
                  <span className="badge badge-lang">{utterance.source_lang}</span>
                </div>
                <p>{text}</p>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

function formatMs(value: number): string {
  const totalSeconds = Math.floor(value / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
