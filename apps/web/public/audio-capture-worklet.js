class AudioCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) {
      return true;
    }

    const channel = input[0];
    if (!channel || channel.length === 0) {
      return true;
    }

    const chunk = new Float32Array(channel.length);
    chunk.set(channel);
    this.port.postMessage(chunk, [chunk.buffer]);
    return true;
  }
}

registerProcessor("audio-capture-processor", AudioCaptureProcessor);
