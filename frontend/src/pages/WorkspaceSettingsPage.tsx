import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api, getErrorMessage } from "@/lib/api";
import type { Workspace, Membership } from "@/types";
import { Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth";

const createSchema = z.object({
  name: z.string().min(2),
  slug: z.string().optional(),
});

const inviteSchema = z.object({
  email: z.string().email(),
  role: z.enum(["admin", "agent", "viewer"]),
});

type CreateForm = z.infer<typeof createSchema>;
type InviteForm = z.infer<typeof inviteSchema>;

export default function WorkspaceSettingsPage() {
  const { workspace } = useOutletContext<{ workspace?: Workspace }>();
  const { user } = useAuth();
  const wsId = workspace?.id;
  const canInvite = workspace?.role === "owner" || workspace?.role === "admin" || workspace?.owner_id === user?.id;
  const canManageMembers = workspace?.role === "owner" || workspace?.role === "admin";
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [showInvite, setShowInvite] = useState(false);

  const createForm = useForm<CreateForm>({ resolver: zodResolver(createSchema) });
  const inviteForm = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: "agent" as const },
  });

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const { data } = await api.get("/workspaces");
      return data.data as Workspace[];
    },
  });

  const { data: members } = useQuery({
    queryKey: ["members", wsId],
    queryFn: async () => {
      const { data } = await api.get(`/workspaces/${wsId}/members`);
      return data.data as Membership[];
    },
    enabled: !!wsId,
  });

  const createWs = useMutation({
    mutationFn: async (form: { name: string; slug?: string }) => {
      const { data } = await api.post("/workspaces", form);
      return data.data as Workspace;
    },
    onSuccess: (ws) => {
      localStorage.setItem("pika_workspace_id", ws.id);
      qc.invalidateQueries({ queryKey: ["workspaces"] });
      createForm.reset();
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const invite = useMutation({
    mutationFn: async (form: { email: string; role: string }) => {
      await api.post(`/workspaces/${wsId}/invitations`, form);
    },
    onSuccess: () => {
      setShowInvite(false);
      inviteForm.reset();
      qc.invalidateQueries({ queryKey: ["members", wsId] });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const removeMember = useMutation({
    mutationFn: async (member: Membership) => {
      await api.delete(`/workspaces/${wsId}/members/${member.user_id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["members", wsId] });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Workspace</h1>
        <p className="text-sm text-slate-500">Manage your team and workspace settings.</p>
      </div>

      {!workspaces?.length && (
        <div className="card p-6">
          <h2 className="font-semibold">Create your first workspace</h2>
          <form
            className="mt-4 space-y-3"
            onSubmit={createForm.handleSubmit((d) => {
              setError("");
              createWs.mutate(d);
            })}
          >
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div>
              <label className="label">Name</label>
              <input className="input" {...createForm.register("name")} />
            </div>
            <div>
              <label className="label">Slug (optional)</label>
              <input className="input" placeholder="my-team" {...createForm.register("slug")} />
            </div>
            <button className="btn-primary" type="submit" disabled={createWs.isPending}>
              Create workspace
            </button>
          </form>
        </div>
      )}

      {workspace && (
        <>
          <div className="card p-6">
            <h2 className="font-semibold text-slate-900">{workspace.name}</h2>
            <p className="text-sm text-slate-500">/{workspace.slug}</p>
            {workspace.description && (
              <p className="mt-2 text-sm text-slate-600">{workspace.description}</p>
            )}
          </div>

          <div className="card">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <h2 className="font-semibold">Members</h2>
              {canInvite && (
                <button className="btn-secondary text-sm" onClick={() => setShowInvite(true)}>
                  <Plus className="h-4 w-4" />
                  Invite
                </button>
              )}
            </div>
            {error && <p className="px-5 pt-3 text-sm text-red-600">{error}</p>}
            <div className="divide-y divide-slate-100">
              {members?.map((m) => (
                <div key={m.id} className="flex items-center gap-3 px-5 py-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                    {m.user?.full_name?.charAt(0) || "?"}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{m.user?.full_name}</p>
                    <p className="text-xs text-slate-500">{m.user?.email}</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium capitalize text-slate-600">
                    {m.role}
                  </span>
                  {canManageMembers && m.role !== "owner" && m.user_id !== user?.id &&
                    (workspace?.role === "owner" || m.role === "agent" || m.role === "viewer") && (
                      <button
                        className="btn-ghost p-2 text-red-600 hover:bg-red-50"
                        aria-label={`Remove ${m.user?.full_name || "member"}`}
                        title="Remove member"
                        disabled={removeMember.isPending}
                        onClick={() => {
                          setError("");
                          removeMember.mutate(m);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {showInvite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="card w-full max-w-md p-6">
            <h2 className="mb-4 text-lg font-semibold">Invite member</h2>
            <form
              className="space-y-3"
              onSubmit={inviteForm.handleSubmit((d) => {
                setError("");
                invite.mutate(d);
              })}
            >
              {error && <p className="text-sm text-red-600">{error}</p>}
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" {...inviteForm.register("email")} />
              </div>
              <div>
                <label className="label">Role</label>
                <select className="input" {...inviteForm.register("role")}>
                  <option value="agent">Agent</option>
                  <option value="admin">Admin</option>
                  <option value="viewer">Viewer</option>
                </select>
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => setShowInvite(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={invite.isPending}>
                  Send invite
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
