import { useEffect, useRef, useState } from "react";

export default function ServiceWorkerUpdatePrompt() {
  const [waitingWorker, setWaitingWorker] = useState<ServiceWorker | null>(null);
  const reloadAfterActivation = useRef(false);

  useEffect(() => {
    if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;

    let registration: ServiceWorkerRegistration | undefined;
    let installingWorker: ServiceWorker | null = null;
    let cancelled = false;

    const onWorkerStateChange = () => {
      if (
        installingWorker?.state === "installed" &&
        navigator.serviceWorker.controller &&
        registration?.waiting
      ) {
        setWaitingWorker(registration.waiting);
      }
    };

    const onUpdateFound = () => {
      installingWorker = registration?.installing ?? null;
      installingWorker?.addEventListener("statechange", onWorkerStateChange);
    };

    const onControllerChange = () => {
      if (!reloadAfterActivation.current) return;
      reloadAfterActivation.current = false;
      window.location.reload();
    };

    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);

    navigator.serviceWorker
      .register("/sw.js", { scope: "/", updateViaCache: "none" })
      .then((serviceWorkerRegistration) => {
        if (cancelled) return;
        registration = serviceWorkerRegistration;
        registration.addEventListener("updatefound", onUpdateFound);

        if (registration.waiting && navigator.serviceWorker.controller) {
          setWaitingWorker(registration.waiting);
        }
      })
      .catch(() => {
        // PWA support is optional; the regular web app must still work.
      });

    return () => {
      cancelled = true;
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
      registration?.removeEventListener("updatefound", onUpdateFound);
      installingWorker?.removeEventListener("statechange", onWorkerStateChange);
    };
  }, []);

  if (!waitingWorker) return null;

  const acceptUpdate = () => {
    reloadAfterActivation.current = true;
    waitingWorker.postMessage({ type: "SKIP_WAITING" });
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl bg-slate-900 px-4 py-3 text-white shadow-xl"
    >
      <p className="text-sm">A new version of Pika is ready.</p>
      <button
        type="button"
        className="shrink-0 rounded-lg bg-white px-3 py-2 text-sm font-medium text-slate-900"
        onClick={acceptUpdate}
      >
        Update
      </button>
      <button
        type="button"
        className="shrink-0 text-sm text-slate-300 hover:text-white"
        onClick={() => setWaitingWorker(null)}
      >
        Later
      </button>
    </div>
  );
}
