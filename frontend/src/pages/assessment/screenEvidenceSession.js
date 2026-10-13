let screenEvidenceStream = null;
const streamListeners = new Set();

function isUsableStream(stream) {
  const track = stream?.getVideoTracks?.()[0];
  return Boolean(track && track.readyState === "live");
}

function clearEndedStream(stream) {
  if (screenEvidenceStream !== stream) return;
  screenEvidenceStream = null;
  streamListeners.forEach((listener) => listener(null));
}

export function getScreenEvidenceStream() {
  if (!isUsableStream(screenEvidenceStream)) {
    if (screenEvidenceStream) {
      screenEvidenceStream.getTracks().forEach((track) => track.stop());
      screenEvidenceStream = null;
    }
    return null;
  }
  return screenEvidenceStream;
}

export async function requestScreenEvidence() {
  const existingStream = getScreenEvidenceStream();
  if (existingStream) return existingStream;

  if (!navigator.mediaDevices?.getDisplayMedia) {
    throw new Error("Screen sharing is not supported by this browser.");
  }

  const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
  if (!isUsableStream(stream)) {
    stream.getTracks().forEach((track) => track.stop());
    throw new Error("Screen sharing did not provide a usable video stream.");
  }

  const videoTrack = stream.getVideoTracks()[0];
  videoTrack.addEventListener("ended", () => clearEndedStream(stream), { once: true });
  screenEvidenceStream = stream;
  streamListeners.forEach((listener) => listener(stream));
  return stream;
}

export function subscribeToScreenEvidence(listener) {
  streamListeners.add(listener);
  listener(getScreenEvidenceStream());
  return () => streamListeners.delete(listener);
}

export function releaseScreenEvidence() {
  const stream = screenEvidenceStream;
  screenEvidenceStream = null;
  if (stream) stream.getTracks().forEach((track) => track.stop());
  streamListeners.forEach((listener) => listener(null));
}

export async function uploadScreenEvidence({ fetchImpl = globalThis.fetch, url, token, formData }) {
  const response = await fetchImpl(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Evidence upload failed (HTTP ${response.status}).`);
  }
  return response;
}