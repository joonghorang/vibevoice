type AudioStreamerOptions = {
  onChunk: (chunk: Float32Array) => void;
  onLevel: (level: number) => void;
};

export class AudioStreamer {
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;

  async start(options: AudioStreamerOptions): Promise<number> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });

    this.audioContext = new AudioContext();
    await this.audioContext.audioWorklet.addModule("/audio-capture-worklet.js");

    this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
    this.workletNode = new AudioWorkletNode(
      this.audioContext,
      "audio-capture-processor",
      {
        numberOfInputs: 1,
        numberOfOutputs: 0,
        channelCount: 1,
      },
    );

    this.workletNode.port.onmessage = (event: MessageEvent<Float32Array>) => {
      const chunk = event.data;
      if (!(chunk instanceof Float32Array)) {
        return;
      }

      options.onLevel(computeRms(chunk));
      options.onChunk(chunk);
    };

    this.sourceNode.connect(this.workletNode);
    return this.audioContext.sampleRate;
  }

  async stop(): Promise<void> {
    this.workletNode?.disconnect();
    this.sourceNode?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());

    if (this.audioContext && this.audioContext.state !== "closed") {
      await this.audioContext.close();
    }

    this.workletNode = null;
    this.sourceNode = null;
    this.stream = null;
    this.audioContext = null;
  }
}

function computeRms(buffer: Float32Array): number {
  let sum = 0;
  for (const sample of buffer) {
    sum += sample * sample;
  }

  return Math.min(1, Math.sqrt(sum / Math.max(buffer.length, 1)));
}
