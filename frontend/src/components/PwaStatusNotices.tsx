import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

export default function PwaStatusNotices() {
  const { isOffline, isAuthenticated } = useAuth();
  const [storageWarning, setStorageWarning] = useState(false);

  useEffect(() => {
    const onStorageQuota = () => setStorageWarning(true);
    window.addEventListener("pika:storage-quota", onStorageQuota);
    return () => window.removeEventListener("pika:storage-quota", onStorageQuota);
  }, []);

  return (
    <>
      {isOffline && isAuthenticated && (
        <div
          role="status"
          className="fixed left-1/2 top-3 z-50 -translate-x-1/2 rounded-lg bg-amber-100 px-4 py-2 text-center text-sm text-amber-900 shadow"
        >
          Offline: showing saved data. Ticket changes need internet for now.
        </div>
      )}
      {storageWarning && (
        <div
          role="status"
          className="fixed bottom-4 left-4 z-50 flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl bg-amber-100 px-4 py-3 text-sm text-amber-950 shadow-xl"
        >
          <span>Device storage is full. Some data could not be saved for offline use.</span>
          <button
            type="button"
            className="shrink-0 font-semibold"
            onClick={() => setStorageWarning(false)}
          >
            Dismiss
          </button>
        </div>
      )}
    </>
  );
}
