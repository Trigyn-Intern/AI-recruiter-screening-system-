export const GAZE_DIRECTIONS = Object.freeze({
  LEFT: "left",
  RIGHT: "right",
  UP: "up",
  DOWN: "down",
  FORWARD: "forward"
});

export const GAZE_DIRECTION_THRESHOLD = 0.16;
export const GAZE_VERTICAL_THRESHOLD = 0.14;
export const GAZE_HYSTERESIS = 0.04;
export const GAZE_SUSTAINED_DURATION_MS = 1500;
export const GAZE_EVENT_COOLDOWN_MS = 3000;
export const GAZE_CALIBRATION_SAMPLES = 3;
export const GAZE_PREVIEW_IS_MIRRORED = true;

const EYE_LANDMARKS = [
  { iris: 468, corners: [33, 133], vertical: [159, 145] },
  { iris: 473, corners: [362, 263], vertical: [386, 374] }
];

function isValidLandmark(landmark) {
  return landmark && Number.isFinite(landmark.x) && Number.isFinite(landmark.y);
}

function getEyePosition(landmarks, eye) {
  const iris = landmarks[eye.iris];
  const corners = eye.corners.map((index) => landmarks[index]);
  const vertical = eye.vertical.map((index) => landmarks[index]);
  const required = [iris, ...corners, ...vertical];

  if (required.some((landmark) => !isValidLandmark(landmark))) return null;

  const minX = Math.min(corners[0].x, corners[1].x);
  const maxX = Math.max(corners[0].x, corners[1].x);
  const minY = Math.min(vertical[0].y, vertical[1].y);
  const maxY = Math.max(vertical[0].y, vertical[1].y);
  const width = maxX - minX;
  const height = maxY - minY;

  if (width < 0.001 || height < 0.001) return null;

  return {
    x: Math.max(0, Math.min(1, (iris.x - minX) / width)),
    y: Math.max(0, Math.min(1, (iris.y - minY) / height))
  };
}

export function getGazePosition(faceLandmarks, isMirrored = GAZE_PREVIEW_IS_MIRRORED) {
  if (!Array.isArray(faceLandmarks)) return null;

  const positions = EYE_LANDMARKS
    .map((eye) => getEyePosition(faceLandmarks, eye))
    .filter(Boolean);

  if (positions.length !== EYE_LANDMARKS.length) return null;

  const averageX = positions.reduce((sum, position) => sum + position.x, 0) / positions.length;
  const averageY = positions.reduce((sum, position) => sum + position.y, 0) / positions.length;

  return {
    x: isMirrored ? 1 - averageX : averageX,
    y: averageY
  };
}

export function updateGazeBaseline(state, position) {
  if (!position || state.baseline || state.calibrationSamples.length >= GAZE_CALIBRATION_SAMPLES) {
    return state.baseline;
  }

  state.calibrationSamples.push(position);
  if (state.calibrationSamples.length < GAZE_CALIBRATION_SAMPLES) return null;

  state.baseline = {
    x: state.calibrationSamples.reduce((sum, sample) => sum + sample.x, 0) / state.calibrationSamples.length,
    y: state.calibrationSamples.reduce((sum, sample) => sum + sample.y, 0) / state.calibrationSamples.length
  };
  return state.baseline;
}

export function classifyGaze(position, baseline, previousDirection = GAZE_DIRECTIONS.FORWARD) {
  if (!position || !baseline) return null;

  const horizontalThreshold = GAZE_DIRECTION_THRESHOLD + (
    previousDirection === GAZE_DIRECTIONS.LEFT || previousDirection === GAZE_DIRECTIONS.RIGHT
      ? GAZE_HYSTERESIS
      : 0
  );
  const verticalThreshold = GAZE_VERTICAL_THRESHOLD + (
    previousDirection === GAZE_DIRECTIONS.UP || previousDirection === GAZE_DIRECTIONS.DOWN
      ? GAZE_HYSTERESIS
      : 0
  );
  const deltaX = position.x - baseline.x;
  const deltaY = position.y - baseline.y;

  if (Math.abs(deltaX) >= horizontalThreshold && Math.abs(deltaX) >= Math.abs(deltaY)) {
    return deltaX < 0 ? GAZE_DIRECTIONS.LEFT : GAZE_DIRECTIONS.RIGHT;
  }
  if (Math.abs(deltaY) >= verticalThreshold) {
    return deltaY < 0 ? GAZE_DIRECTIONS.UP : GAZE_DIRECTIONS.DOWN;
  }
  return GAZE_DIRECTIONS.FORWARD;
}

export function createGazeState() {
  return {
    baseline: null,
    calibrationSamples: [],
    stableDirection: null,
    pendingDirection: null,
    pendingSince: null,
    lastEventTimes: {}
  };
}

export function resetGazeTracking(state) {
  state.stableDirection = null;
  state.pendingDirection = null;
  state.pendingSince = null;
}

export function updateGazeState(state, direction, now = Date.now()) {
  if (!direction) {
    resetGazeTracking(state);
    return null;
  }

  if (direction !== state.pendingDirection) {
    state.pendingDirection = direction;
    state.pendingSince = now;
    return null;
  }

  if (state.pendingSince === null || now - state.pendingSince < GAZE_SUSTAINED_DURATION_MS) {
    return null;
  }

  if (direction === state.stableDirection) return null;

  state.stableDirection = direction;
  const lastEventTime = state.lastEventTimes[direction];
  if (lastEventTime !== undefined && now - lastEventTime < GAZE_EVENT_COOLDOWN_MS) return null;

  state.lastEventTimes[direction] = now;
  return direction;
}