import { useQuery } from "@tanstack/react-query";
import { useOutletContext, Link } from "react-router-dom";
import { api, isNetworkUnavailable } from "@/lib/api";
import { cacheRecords, getCachedRecords } from "@/lib/offlineDb";
import { useAuth } from "@/lib/auth";
import type { Workspace, WorkspaceStats, Ticket } from "@/types";
import { STATUS_COLORS, PRIORITY_COLORS, relativeTime, statusLabel, cn } from "@/lib/utils";
import { Ticket as TicketIcon, Clock, UserX, AlertCircle } from "lucide-react";

export default function DashboardPage() {
  const { workspace } = useOutletContext<{ workspace?: Workspace }>();
  const { user } = useAuth();
  const wsId = workspace?.id;

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["stats", wsId],
    queryFn: async () => {
      const { data } = await api.get(`/workspaces/${wsId}/stats`);
      return data.data as WorkspaceStats;
    },
    enabled: !!wsId,
  });

  const { data: recent } = useQuery({
    queryKey: ["tickets", wsId, "recent"],
    queryFn: async () => {
      try {
        const response = await api.get("/workspaces/" + wsId + "/tickets", {
          params: { per_page: 5, sort: "-updated_at" },
        });
        const tickets = response.data.data as Ticket[];
        if (user) {
          await cacheRecords(user.id, wsId!, "ticket", tickets).catch(() => undefined);
        }
        return tickets;
      } catch (error) {
        if (!user || !isNetworkUnavailable(error)) throw error;
        const cachedTickets = await getCachedRecords<Ticket>(user.id, wsId!, "ticket");
        return cachedTickets
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
          .slice(0, 5);
      }
    },
    enabled: !!wsId && !!user,
  });

  if (!wsId) {
    return (
      <div className="card p-8 text-center">
        <h2 className="text-lg font-semibold">No workspace yet</h2>
        <p className="mt-2 text-sm text-slate-500">
          Create a workspace to start managing tickets.
        </p>
        <Link to="/workspace" className="btn-primary mt-4 inline-flex">
          Create workspace
        </Link>
      </div>
    );
  }

  const cards = [
    { label: "Open tickets", value: stats?.open ?? "—", icon: TicketIcon, color: "text-blue-600 bg-blue-50" },
    { label: "Assigned to me", value: stats?.my_open ?? "—", icon: Clock, color: "text-amber-600 bg-amber-50" },
    { label: "Unassigned", value: stats?.unassigned ?? "—", icon: UserX, color: "text-purple-600 bg-purple-50" },
    { label: "Total", value: stats?.total ?? "—", icon: AlertCircle, color: "text-slate-600 bg-slate-100" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500">{workspace?.name}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className="card p-5">
            <div className="flex items-center gap-3">
              <div className={cn("rounded-lg p-2.5", c.color)}>
                <c.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-slate-500">{c.label}</p>
                <p className="text-2xl font-semibold text-slate-900">
                  {statsLoading ? "…" : c.value}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="font-semibold text-slate-900">Recent tickets</h2>
          <Link to="/tickets" className="text-sm font-medium text-brand-600 hover:text-brand-700">
            View all
          </Link>
        </div>
        <div className="divide-y divide-slate-100">
          {!recent?.length && (
            <p className="px-5 py-8 text-center text-sm text-slate-500">No tickets yet.</p>
          )}
          {recent?.map((t) => (
            <Link
              key={t.id}
              to={`/tickets/${t.id}`}
              className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 transition-colors"
            >
              <span className="text-sm font-medium text-slate-400">#{t.number}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900">{t.title}</p>
                <p className="text-xs text-slate-500">{relativeTime(t.updated_at)}</p>
              </div>
              <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium capitalize", STATUS_COLORS[t.status])}>
                {statusLabel(t.status)}
              </span>
              <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium capitalize", PRIORITY_COLORS[t.priority])}>
                {t.priority}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
