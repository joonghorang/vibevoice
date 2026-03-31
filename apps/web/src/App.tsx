import { useEffect, useMemo, useState } from "react";
import { HeaderBar } from "./components/header-bar";
import { SubtitlePane } from "./components/subtitle-pane";
import { useLiveSession } from "./hooks/use-live-session";

export default function App() {
  const {
    snapshot,
    isConnecting,
    isProcessingFile,
    clientLevel,
    sampleFiles,
    startSession,
    stopSession,
    processSample,
    uploadAudioFile,
  } = useLiveSession();

  const [hotwordsText, setHotwordsText] = useState("");
  const [autoFollow, setAutoFollow] = useState(true);
  const [selectedSampleName, setSelectedSampleName] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const hotwords = useMemo(
    () =>
      hotwordsText
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
    [hotwordsText],
  );

  useEffect(() => {
    if (!selectedSampleName && sampleFiles.length > 0) {
      setSelectedSampleName(sampleFiles[0].name);
    }
  }, [sampleFiles, selectedSampleName]);

  return (
    <div className="app-shell">
      <div className="backdrop" />
      <main className="app-frame">
        <HeaderBar
          snapshot={snapshot}
          clientLevel={clientLevel}
          isConnecting={isConnecting || isProcessingFile}
          hotwordsText={hotwordsText}
          onHotwordsChange={setHotwordsText}
          onStart={() => {
            setAutoFollow(true);
            void startSession({ hotwords });
          }}
          onStop={() => void stopSession()}
        />

        <section className="test-panel">
          <div className="test-card">
            <p className="pane-eyebrow">Bundled Sample</p>
            <h3>Run The Included VibeVoice Demo Audio</h3>
            <p>
              Process the sample file already stored in the workspace to test
              transcription and translation without a microphone.
            </p>
            <div className="inline-controls">
              <select
                value={selectedSampleName}
                onChange={(event) => setSelectedSampleName(event.target.value)}
                disabled={sampleFiles.length === 0 || isProcessingFile}
              >
                {sampleFiles.length === 0 ? (
                  <option value="">No sample files found</option>
                ) : (
                  sampleFiles.map((sample) => (
                    <option key={sample.name} value={sample.name}>
                      {sample.name}
                    </option>
                  ))
                )}
              </select>
              <button
                className="secondary-button"
                disabled={!selectedSampleName || isProcessingFile}
                onClick={() => {
                  setAutoFollow(true);
                  void processSample(selectedSampleName, hotwords);
                }}
              >
                {isProcessingFile ? "Processing..." : "Process Sample"}
              </button>
            </div>
          </div>

          <div className="test-card">
            <p className="pane-eyebrow">Upload Audio</p>
            <h3>Test With Your Own PCM WAV File</h3>
            <p>
              Upload a local recording in WAV format and render the full
              transcript into the split-screen viewer.
            </p>
            <div className="inline-controls">
              <input
                type="file"
                accept=".wav,audio/wav"
                onChange={(event) =>
                  setSelectedFile(event.target.files?.[0] ?? null)
                }
              />
              <button
                className="secondary-button"
                disabled={!selectedFile || isProcessingFile}
                onClick={() => {
                  if (!selectedFile) {
                    return;
                  }
                  setAutoFollow(true);
                  void uploadAudioFile(selectedFile, hotwords);
                }}
              >
                {isProcessingFile ? "Processing..." : "Upload And Process"}
              </button>
            </div>
            <span className="helper-text">
              Recommended: mono PCM WAV. The bundled sample is already 24 kHz
              mono and ready to use.
            </span>
          </div>
        </section>

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
