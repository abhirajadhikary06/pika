import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useOutletContext } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api, getErrorMessage } from "@/lib/api";
import type { Workspace, Ticket } from "@/types";
import { STATUS_COLORS, PRIORITY_COLORS, relativeTime, statusLabel, cn } from "@/lib/utils";
import { Plus, Search, X } from "lucide-react";

const createSchema = z.object({
  title: z.string().min(3, "Title must be at least 3 characters"),
  description: z.string().optional(),
  priority: z.enum(["low", "medium", "high", "urgent"]),
  type: z.enum(["question", "incident", "problem", "task"]),
});

type CreateForm = z.infer<typeof createSchema>;

export default function TicketsPage() {
  const { workspace } = useOutletContext<{ workspace?: Workspace }>();
  const wsId = workspace?.id;
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["tickets", wsId, statusFilter, search],
    queryFn: async () => {
      const { data } = await api.get(`/workspaces/${wsId}/tickets`, {
        params: {
          status: statusFilter || undefined,
          q: search || undefined,
          per_page: 50,
        },
      });
      return data as { data: Ticket[]; meta: { total: number } };
    },
    enabled: !!wsId,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { priority: "medium", type: "question" },
  });

  const createMutation = useMutation({
    mutationFn: async (form: CreateForm) => {
      const { data } = await api.post(`/workspaces/${wsId}/tickets`, form);
      return data.data as Ticket;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets", wsId] });
      qc.invalidateQueries({ queryKey: ["stats", wsId] });
      setShowCreate(false);
      reset();
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (!wsId) {
    return <p className="text-slate-500">Select or create a workspace first.</p>;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Tickets</h1>
          <p className="text-sm text-slate-500">{data?.meta?.total ?? 0} total</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" />
          New ticket
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            className="input pl-9"
            placeholder="Search tickets…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="input w-auto"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="pending">Pending</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
          </div>
        ) : !data?.data?.length ? (
          <p className="py-16 text-center text-sm text-slate-500">No tickets found.</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {data.data.map((t) => (
              <Link
                key={t.id}
                to={`/tickets/${t.id}`}
                className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 transition-colors"
              >
                <span className="w-12 shrink-0 text-sm font-medium text-slate-400">#{t.number}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">{t.title}</p>
                  <p className="text-xs text-slate-500">
                    {t.assignee ? `Assigned to ${t.assignee.full_name}` : "Unassigned"} ·{" "}
                    {relativeTime(t.updated_at)}
                  </p>
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
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="card w-full max-w-lg p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">New ticket</h2>
              <button onClick={() => setShowCreate(false)} className="rounded-lg p-1 hover:bg-slate-100">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form
              onSubmit={handleSubmit((d) => {
                setError("");
                createMutation.mutate(d);
              })}
              className="space-y-4"
            >
              {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
              <div>
                <label className="label">Title</label>
                <input className="input" {...register("title")} />
                {errors.title && <p className="mt-1 text-xs text-red-600">{errors.title.message}</p>}
              </div>
              <div>
                <label className="label">Description</label>
                <textarea className="input min-h-[100px]" {...register("description")} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Priority</label>
                  <select className="input" {...register("priority")}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
                <div>
                  <label className="label">Type</label>
                  <select className="input" {...register("type")}>
                    <option value="question">Question</option>
                    <option value="incident">Incident</option>
                    <option value="problem">Problem</option>
                    <option value="task">Task</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? "Creating…" : "Create ticket"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
