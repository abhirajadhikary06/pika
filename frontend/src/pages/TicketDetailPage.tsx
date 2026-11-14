import { useState } from "react";
import { useParams, useOutletContext, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getErrorMessage, isNetworkUnavailable } from "@/lib/api";
import { cacheRecords, getCachedRecord } from "@/lib/offlineDb";
import { useAuth } from "@/lib/auth";
import type { Workspace, Ticket, Comment } from "@/types";
import { STATUS_COLORS, PRIORITY_COLORS, relativeTime, formatDate, statusLabel, cn } from "@/lib/utils";
import { ArrowLeft, Download, Paperclip, Send } from "lucide-react";

export default function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const { workspace } = useOutletContext<{ workspace?: Workspace }>();
  const { user, isOffline } = useAuth();
  const canSeeInternalNotes = ["owner", "admin", "agent"].includes(workspace?.role || "");
  const wsId = workspace?.id;
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  const { data: ticket, isLoading } = useQuery({
    queryKey: ["ticket", wsId, ticketId],
    queryFn: async () => {
      try {
        const response = await api.get("/workspaces/" + wsId + "/tickets/" + ticketId);
        const ticket = response.data.data as Ticket;
        if (user) {
          await cacheRecords(user.id, wsId!, "ticket-detail", [ticket]).catch(() => undefined);
        }
        return ticket;
      } catch (error) {
        if (!user || !isNetworkUnavailable(error)) throw error;
        const detailedTicket = await getCachedRecord<Ticket>(user.id, wsId!, "ticket-detail", ticketId!);
        return detailedTicket || getCachedRecord<Ticket>(user.id, wsId!, "ticket", ticketId!);
      }
    },
    enabled: !!wsId && !!ticketId && !!user,
  });

  const updateMutation = useMutation({
    mutationFn: async (payload: Partial<Ticket>) => {
      const { data } = await api.patch(`/workspaces/${wsId}/tickets/${ticketId}`, payload);
      return data.data as Ticket;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ticket", wsId, ticketId] });
      qc.invalidateQueries({ queryKey: ["tickets", wsId] });
      qc.invalidateQueries({ queryKey: ["stats", wsId] });
    },
  });

  const uploadAttachment = async (file: File) => {
    if (!wsId || !ticketId) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      await api.post(`/workspaces/${wsId}/tickets/${ticketId}/attachments`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      qc.invalidateQueries({ queryKey: ["ticket", wsId, ticketId] });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const downloadAttachment = async (attachmentId: string, filename: string) => {
    if (!wsId || !ticketId) return;
    try {
      const response = await api.get(
        `/workspaces/${wsId}/tickets/${ticketId}/attachments/${attachmentId}`,
        { responseType: "blob" }
      );
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const commentMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/workspaces/${wsId}/tickets/${ticketId}/comments`, {
        body,
        is_internal: isInternal,
      });

      return data.data as Comment;
    },
    onSuccess: () => {
      setBody("");
      setIsInternal(false);
      qc.invalidateQueries({ queryKey: ["ticket", wsId, ticketId] });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
      </div>
    );
  }
  if (!ticket) {
    return <p className="py-12 text-center text-sm text-slate-500">This ticket has not been saved on this device. Connect to the internet to load it.</p>;
  }

  const comments = [
    ...(ticket.comments || []),
    ...(canSeeInternalNotes ? ticket.internal_notes || [] : []),
  ].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/tickets" className="btn-ghost p-2">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-slate-400">#{ticket.number}</span>
            <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium capitalize", STATUS_COLORS[ticket.status])}>
              {statusLabel(ticket.status)}
            </span>
            <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium capitalize", PRIORITY_COLORS[ticket.priority])}>
              {ticket.priority}
            </span>
          </div>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">{ticket.title}</h1>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          {ticket.description && (
            <div className="card p-5">
              <p className="whitespace-pre-wrap text-sm text-slate-700">{ticket.description}</p>
            </div>
          )}

          <div className="card">
            <div className="border-b border-slate-100 px-5 py-3">
              <h2 className="font-semibold text-slate-900">Conversation</h2>
            </div>
            <div className="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
              {comments.length === 0 && (
                <p className="px-5 py-8 text-center text-sm text-slate-500">No replies yet.</p>
              )}
              {comments.map((c) => (
                <div key={c.id} className={cn("px-5 py-4", c.is_internal && "bg-amber-50/50")}>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-900">
                      {c.author?.full_name || "Unknown"}
                    </span>
                    {c.is_internal && (
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-amber-800">
                        Internal
                      </span>
                    )}
                    <span className="text-xs text-slate-400">{relativeTime(c.created_at)}</span>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{c.body}</p>
                </div>
              ))}
            </div>
            <div className="border-t border-slate-100 p-4">
              {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
              <textarea
                className="input min-h-[80px]"
                placeholder="Write a reply…"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                disabled={isOffline}
              />
              <div className="mt-2 flex items-center justify-between">
                {canSeeInternalNotes ? (
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={isInternal}
                      disabled={isOffline}
                      onChange={(e) => setIsInternal(e.target.checked)}
                      className="rounded border-slate-300"
                    />
                    Internal note
                  </label>
                ) : <span />}
                <div className="flex items-center gap-2">
                  <label className="btn-secondary cursor-pointer">
                    <Paperclip className="h-4 w-4" />
                    {uploading ? "Uploading…" : "Attach"}
                    <input
                      type="file"
                      className="hidden"
                      disabled={uploading || isOffline}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void uploadAttachment(file);
                        event.target.value = "";
                      }}
                    />
                  </label>
                  <button
                  className="btn-primary"
                  disabled={!body.trim() || commentMutation.isPending || isOffline}
                  onClick={() => {
                    setError("");
                    commentMutation.mutate();
                  }}
                >
                  <Send className="h-4 w-4" />
                  {commentMutation.isPending ? "Sending…" : "Send"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {!!ticket.attachments?.length && (
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">Attachments</h3>
              <ul className="space-y-2">
                {ticket.attachments.map((attachment) => (
                  <li key={attachment.id} className="flex items-center gap-2 text-sm">
                    <Paperclip className="h-4 w-4 text-slate-400" />
                    <button
                      className="min-w-0 flex-1 truncate text-left text-brand-700 hover:underline disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={isOffline}
                      onClick={() => void downloadAttachment(attachment.id, attachment.original_filename)}
                    >
                      {attachment.original_filename}
                    </button>
                    <Download className="h-4 w-4 text-slate-400" />
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="card p-5 space-y-4">
            <div>
              <label className="label">Status</label>
              <select
                className="input"
                value={ticket.status}
                disabled={isOffline}
                onChange={(e) => updateMutation.mutate({ status: e.target.value as Ticket["status"] })}
              >
                <option value="open">Open</option>
                <option value="in_progress">In progress</option>
                <option value="pending">Pending</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
            </div>
            <div>
              <label className="label">Priority</label>
              <select
                className="input"
                value={ticket.priority}
                disabled={isOffline}
                onChange={(e) => updateMutation.mutate({ priority: e.target.value as Ticket["priority"] })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
            <div className="text-sm text-slate-500 space-y-1 pt-2 border-t border-slate-100">
              <p>Created {formatDate(ticket.created_at)}</p>
              <p>Updated {formatDate(ticket.updated_at)}</p>
              {ticket.created_by && <p>By {ticket.created_by.full_name}</p>}
              {ticket.assignee && <p>Assigned to {ticket.assignee.full_name}</p>}
            </div>
          </div>

          {ticket.activities && ticket.activities.length > 0 && (
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">Activity</h3>
              <ul className="space-y-2">
                {ticket.activities.slice(0, 1).map((a) => (
                  <li key={a.id} className="text-xs text-slate-600">
                    <span className="font-medium">{a.actor?.full_name || "System"}</span>{" "}
                    {a.action.replace("_", " ")} · {relativeTime(a.created_at)}
                  </li>
                ))}
              </ul>
              {ticket.activities.length > 1 && (
                <details className="mt-3 border-t border-slate-100 pt-3">
                  <summary className="cursor-pointer text-xs font-medium text-brand-700 hover:text-brand-800">
                    Show {ticket.activities.length - 1} more
                  </summary>
                  <ul className="mt-3 space-y-2">
                    {ticket.activities.slice(1).map((a) => (
                      <li key={a.id} className="text-xs text-slate-600">
                        <span className="font-medium">{a.actor?.full_name || "System"}</span>{" "}
                        {a.action.replace("_", " ")} · {relativeTime(a.created_at)}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
