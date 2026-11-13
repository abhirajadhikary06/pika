import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import type { Notification } from "@/types";
import { relativeTime, cn } from "@/lib/utils";
import { Bell } from "lucide-react";

export default function NotificationsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => {
      const { data } = await api.get("/notifications", { params: { per_page: 50 } });
      return data as { data: Notification[]; meta: { unread_count: number } };
    },
  });

  const markRead = useMutation({
    mutationFn: async (id: string) => {
      await api.post(`/notifications/${id}/read`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const markAll = useMutation({
    mutationFn: async () => {
      await api.post("/notifications/read-all");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Notifications</h1>
          <p className="text-sm text-slate-500">
            {data?.meta?.unread_count ?? 0} unread
          </p>
        </div>
        {(data?.meta?.unread_count ?? 0) > 0 && (
          <button className="btn-secondary text-sm" onClick={() => markAll.mutate()}>
            Mark all read
          </button>
        )}
      </div>

      <div className="card divide-y divide-slate-100">
        {isLoading && (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
          </div>
        )}
        {!isLoading && !data?.data?.length && (
          <div className="flex flex-col items-center py-16 text-slate-500">
            <Bell className="mb-2 h-8 w-8 opacity-40" />
            <p className="text-sm">No notifications yet.</p>
          </div>
        )}
        {data?.data?.map((n) => (
          <button
            key={n.id}
            className={cn(
              "flex w-full items-start gap-3 px-5 py-4 text-left hover:bg-slate-50 transition-colors",
              !n.is_read && "bg-brand-50/40"
            )}
            onClick={() => {
              if (!n.is_read) markRead.mutate(n.id);
              const token = n.data?.invitation_token;
              if (n.type === "invitation" && typeof token === "string") {
                navigate(`/invite/${token}`);
              }
            }}
          >
            <div
              className={cn(
                "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                n.is_read ? "bg-transparent" : "bg-brand-500"
              )}
            />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-900">{n.title}</p>
              {n.body && <p className="mt-0.5 text-sm text-slate-600 line-clamp-2">{n.body}</p>}
              <p className="mt-1 text-xs text-slate-400">{relativeTime(n.created_at)}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
