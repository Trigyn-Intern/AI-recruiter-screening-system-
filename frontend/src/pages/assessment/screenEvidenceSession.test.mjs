import assert from "node:assert/strict";
import test from "node:test";

import {
  getScreenEvidenceStream,
  releaseScreenEvidence,
  requestScreenEvidence,
  uploadScreenEvidence,
} from "./screenEvidenceSession.js";

function createTrack() {
  const listeners = new Map();
  return {
    readyState: "live",
    addEventListener(type, listener) {
      listeners.set(type, listener);
    },
    stop() {
      this.readyState = "ended";
    },
    end() {
      this.readyState = "ended";
      listeners.get("ended")?.();
    },
  };
}

function createStream(track) {
  return {
    getVideoTracks: () => [track],
    getTracks: () => [track],
  };
}

test("returns no stream when none has been requested", () => {
  releaseScreenEvidence();
  assert.equal(getScreenEvidenceStream(), null);
});

test("reuses a live stream and clears it when the track ends", async () => {
  releaseScreenEvidence();
  const track = createTrack();
  const stream = createStream(track);
  let requests = 0;
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
    mediaDevices: {
      getDisplayMedia: async () => {
        requests += 1;
        return stream;
      },
    },
    },
  });

  const first = await requestScreenEvidence();
  const second = await requestScreenEvidence();
  assert.equal(first, stream);
  assert.equal(second, stream);
  assert.equal(requests, 1);

  track.end();
  assert.equal(getScreenEvidenceStream(), null);
});

test("drops stopped tracks without creating a replacement stream", () => {
  releaseScreenEvidence();
  const track = createTrack();
  track.readyState = "ended";
  const stream = createStream(track);
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { mediaDevices: { getDisplayMedia: async () => stream } },
  });
  assert.equal(getScreenEvidenceStream(), null);
});

test("reports a non-successful evidence upload", async () => {
  await assert.rejects(
    uploadScreenEvidence({
      fetchImpl: async () => ({
        ok: false,
        status: 503,
        json: async () => ({ detail: "storage unavailable" }),
      }),
      url: "/evidence",
      token: "assessment-token",
      formData: {},
    }),
    /storage unavailable/
  );
});