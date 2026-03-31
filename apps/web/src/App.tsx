import { useMemo, useState } from "react";
import { HeaderBar } from "./components/header-bar";
import { SubtitlePane } from "./components/subtitle-pane";
import { useLiveSession } from "./hooks/use-live-session";

export default function App() {
  const { snapshot, isConnecting, clientLevel, startSession, stopSession } =
    useLiveSession();

  const [hotwordsText, setHotwordsText] = useState("");
  const [autoFollow, setAutoFollow] = useState(true);

  const hotwords = useMemo(
    () =>
      hotwordsText
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
    [hotwordsText],
  );

  return (
    <div className="app-shell">
      <div className="backdrop" />
      <main className="app-frame">
        <HeaderBar
          snapshot={snapshot}
          clientLevel={clientLevel}
          isConnecting={isConnecting}
          hotwordsText={hotwordsText}
          onHotwordsChange={setHotwordsText}
          onStart={() => {
            setAutoFollow(true);
            void startSession({ hotwords });
          }}
          onStop={() => void stopSession()}
        />

        <section className="status-banner">
          <div>
            <strong>{snapshot.utterances.length}</strong>
            <span>captured utterances</span>
          </div>
          <div>
            <strong>{snapshot.hotwords.length}</strong>
            <span>active hotwords</span>
          </div>
          <div>
            <strong>{Math.round(snapshot.audio_level * 100)}%</strong>
            <span>server audio level</span>
          </div>
          <button
            className="ghost-button"
            onClick={() => setAutoFollow(true)}
            disabled={autoFollow}
          >
            {autoFollow ? "Auto-follow on" : "Return to live line"}
          </button>
        </section>

        {snapshot.last_error ? (
          <section className="error-banner">{snapshot.last_error}</section>
        ) : null}

        <section className="split-layout">
          <SubtitlePane
            title="Source Text"
            mode="source"
            utterances={snapshot.utterances}
            activeUtteranceId={snapshot.active_utterance_id}
            autoFollow={autoFollow}
            onPauseAutoFollow={() => setAutoFollow(false)}
          />
          <SubtitlePane
            title="Translated Text"
            mode="translation"
            utterances={snapshot.utterances}
            activeUtteranceId={snapshot.active_utterance_id}
            autoFollow={autoFollow}
            onPauseAutoFollow={() => setAutoFollow(false)}
          />
        </section>
      </main>
    </div>
  );
}
