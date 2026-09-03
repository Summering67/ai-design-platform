type ScheduleFrame = (callback: () => void) => number;
type CancelFrame = (handle: number) => void;

type FrameBuffer<T> = {
  enqueue: (value: T) => void;
  flush: () => void;
  discard: () => void;
  dispose: () => void;
};

const browserSchedule: ScheduleFrame = (callback) =>
  window.requestAnimationFrame(callback);
const browserCancel: CancelFrame = (handle) => window.cancelAnimationFrame(handle);

const createFrameBuffer = <T,>(
  onFlush: (values: readonly T[]) => void,
  schedule: ScheduleFrame = browserSchedule,
  cancel: CancelFrame = browserCancel,
): FrameBuffer<T> => {
  let values: T[] = [];
  let frame: number | null = null;
  let disposed = false;

  const flush = () => {
    if (frame !== null) {
      cancel(frame);
      frame = null;
    }
    if (disposed || !values.length) return;
    const batch = values;
    values = [];
    onFlush(batch);
  };
  const enqueue = (value: T) => {
    if (disposed) return;
    values.push(value);
    if (frame === null) frame = schedule(flush);
  };
  const discard = () => {
    if (frame !== null) {
      cancel(frame);
      frame = null;
    }
    values = [];
  };
  const dispose = () => {
    discard();
    disposed = true;
  };

  return { enqueue, flush, discard, dispose };
};

export { createFrameBuffer };
export type { FrameBuffer, ScheduleFrame, CancelFrame };
