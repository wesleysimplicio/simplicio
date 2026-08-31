/**
 * One native read at a time, with a bounded wait for its observers.
 * A timeout is not cancellation: retain the slot until the native call settles.
 * Never use this wrapper for installation, authentication or other effects.
 */
export function createReadonlyRequest<T>(timeoutMs: number, timeoutCode: string) {
  let pending: Promise<T> | undefined;

  return (start: () => Promise<T>): Promise<T> => {
    if (pending) return pending;
    // Normalize a synchronous throw, and never begin another read automatically.
    const native = Promise.resolve().then(start);
    pending = new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(timeoutCode)), timeoutMs);
      native.then(
        (value) => { clearTimeout(timer); pending = undefined; resolve(value); },
        (error: unknown) => { clearTimeout(timer); pending = undefined; reject(error); },
      );
    });
    return pending;
  };
}
