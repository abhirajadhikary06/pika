import { api } from "@/lib/api";
import {
  enqueueOfflineWrites, offlineDb, type CachedRecord, type OutboxOperation,
} from "@/lib/offlineDb";
import type { Comment, Ticket } from "@/types";

type PushResult = {
  op_id: string;
  status: "synced" | "conflict" | "failed";
  result?: Ticket | Comment;
  server?: Ticket;
  local?: Record<string, unknown>;
  error?: string;
};

const activeSyncs = new Map<string, Promise<void>>();
const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;

function signalSyncChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("pika:sync-updated"));
}

function newId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const value = Math.floor(Math.random() * 16);
    return (char === "x" ? value : (value & 0x3) | 0x8).toString(16);
  });
}

export async function queueTicketCreate(userId: string, workspaceId: string, input: Partial<Ticket>) {
  const now = new Date().toISOString();
  const id = newId();
  const ticket: Ticket = {
    id, workspace_id: workspaceId, number: 0,
    title: input.title || "", description: input.description || null,
    status: "open", priority: input.priority || "medium", type: input.type || "question",
    tags: input.tags || [], version: 1, created_at: now, updated_at: now,
    client_id: id,
  };
  const opId = newId();
  const op: Omit<OutboxOperation, "status" | "createdAt" | "attempts"> = {
    opId, userId, workspaceId, recordId: id, recordType: "ticket", operation: "create", payload: ticket,
  };
  await enqueueOfflineWrites(op, [{
    userId, workspaceId, kind: "ticket", recordId: id, version: 1, deleted: false,
    updatedAt: now, payload: ticket,
  }]);
  signalSyncChanged();
  void syncWorkspace(userId, workspaceId).catch(() => undefined);
  return ticket;
}

export async function queueTicketComment(
  userId: string, workspaceId: string, ticket: Ticket, body: string, isInternal = false,
) {
  const now = new Date().toISOString();
  const comment: Comment = {
    id: newId(), ticket_id: ticket.id, body, is_internal: isInternal,
    version: 1, created_at: now, updated_at: now,
  };
  const detail = {
    ...ticket,
    comments: [...(ticket.comments || []), ...(isInternal ? [] : [comment])],
    internal_notes: [...(ticket.internal_notes || []), ...(isInternal ? [comment] : [])],
  };
  const op: Omit<OutboxOperation, "status" | "createdAt" | "attempts"> = {
    opId: newId(), userId, workspaceId, recordId: comment.id,
    recordType: "comment", operation: "create", payload: comment,
  };
  await enqueueOfflineWrites(op, [{
    userId, workspaceId, kind: "ticket-detail", recordId: ticket.id,
    version: ticket.version, deleted: false, updatedAt: now, payload: detail,
  }]);
  signalSyncChanged();
  void syncWorkspace(userId, workspaceId).catch(() => undefined);
  return comment;
}

export async function queueTicketUpdate(
  userId: string, workspaceId: string, ticket: Ticket, changes: Partial<Ticket>,
) {
  const now = new Date().toISOString();
  const updated = { ...ticket, ...changes, updated_at: now };
  const op: Omit<OutboxOperation, "status" | "createdAt" | "attempts"> = {
    opId: newId(), userId, workspaceId, recordId: ticket.id,
    recordType: "ticket", operation: "update", payload: { id: ticket.id, changes },
    baseVersion: ticket.version, baseSnapshot: ticket as unknown as Record<string, unknown>,
  };
  await enqueueOfflineWrites(op, ["ticket", "ticket-detail"].map((kind) => ({
    userId, workspaceId, kind: kind as CachedRecord["kind"], recordId: ticket.id,
    version: ticket.version, deleted: false, updatedAt: now, payload: updated,
  })));
  signalSyncChanged();
  void syncWorkspace(userId, workspaceId).catch(() => undefined);
  return updated;
}

async function applyPulledChanges(userId: string, workspaceId: string, changes: Array<{
  cursor: number; entity_type: "ticket" | "comment"; entity_id: string;
  operation: string; version: number; payload: Ticket | Comment | null;
}>) {
  for (const change of changes) {
    const dirty = await offlineDb.outbox.where("[userId+workspaceId]")
      .equals([userId, workspaceId]).filter((op) => op.recordId === change.entity_id && op.status !== "synced").count();
    if (dirty) continue;
    if (change.operation === "delete") {
      for (const kind of ["ticket", "ticket-detail"] as const) {
        const record = await offlineDb.records.get([userId, workspaceId, kind, change.entity_id]);
        if (record) await offlineDb.records.put({ ...record, deleted: true, version: change.version });
      }
      continue;
    }
    if (change.entity_type === "ticket" && change.payload) {
      const ticket = change.payload as Ticket;
      const record: CachedRecord<Ticket> = {
        userId, workspaceId, kind: "ticket", recordId: ticket.id,
        version: ticket.version, deleted: false, updatedAt: ticket.updated_at, payload: ticket,
      };
      await offlineDb.records.put(record);
      const detail = await offlineDb.records.get([userId, workspaceId, "ticket-detail", ticket.id]);
      if (detail && (detail.version <= ticket.version)) {
        await offlineDb.records.put({ ...detail, version: ticket.version, updatedAt: ticket.updated_at,
          payload: { ...(detail.payload as Ticket), ...ticket } });
      }
    } else if (change.entity_type === "comment" && change.payload) {
      const comment = change.payload as Comment;
      const detail = await offlineDb.records.get([userId, workspaceId, "ticket-detail", comment.ticket_id]);
      if (detail) {
        const ticket = detail.payload as Ticket;
        const key = comment.is_internal ? "internal_notes" : "comments";
        const list = (ticket[key] || []) as Comment[];
        if (!list.some((entry) => entry.id === comment.id)) {
          await offlineDb.records.put({ ...detail, payload: { ...ticket, [key]: [...list, comment] } });
        }
      }
    }
  }
}

async function pullChanges(userId: string, workspaceId: string) {
  const metaKey = "sync-cursor";
  const meta = await offlineDb.meta.get([userId, workspaceId, metaKey]);
  let cursor = Number(meta?.value || 0);
  let more = true;
  while (more) {
    const { data } = await api.get(`/workspaces/${workspaceId}/sync/pull`, { params: { cursor, limit: 100 } });
    const result = data.data as { changes: Parameters<typeof applyPulledChanges>[2]; cursor: number; has_more: boolean };
    await applyPulledChanges(userId, workspaceId, result.changes);
    cursor = result.cursor;
    more = result.has_more;
  }
  await offlineDb.meta.put({ userId, workspaceId, key: metaKey, value: cursor, updatedAt: new Date().toISOString() });
}

function mergeNonConflicting(op: OutboxOperation, server: Ticket, localChanges: Record<string, unknown>) {
  const base = op.baseSnapshot || {};
  const equal = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
  const conflicts = Object.keys(localChanges).filter((field) =>
    !equal(server[field as keyof Ticket], base[field]) && !equal(server[field as keyof Ticket], localChanges[field]));
  if (conflicts.length) return false;
  op.baseVersion = server.version;
  op.baseSnapshot = server as unknown as Record<string, unknown>;
  return true;
}

async function runSync(userId: string, workspaceId: string) {
  const syncedCutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
  await offlineDb.outbox.where("[userId+workspaceId]").equals([userId, workspaceId])
    .filter((op) => op.status === "synced" && op.createdAt < syncedCutoff).delete();
  await offlineDb.outbox.where("[userId+workspaceId]").equals([userId, workspaceId])
    .filter((op) => op.status === "inflight").modify({ status: "pending" });
  const all = await offlineDb.outbox.where("[userId+workspaceId]").equals([userId, workspaceId]).toArray();
  const now = Date.now();
  const ops = all.filter((op) => op.status === "pending" || (op.status === "failed" && (!op.nextAttemptAt || Date.parse(op.nextAttemptAt) <= now)))
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  if (!ops.length) {
    await pullChanges(userId, workspaceId);
    return;
  }
  for (const op of ops) await offlineDb.outbox.update(op.opId, { status: "inflight" });
  let hasAutoMerge = false;
  try {
    const { data } = await api.post(`/workspaces/${workspaceId}/sync/push`, { operations: ops.map((op) => ({
      op_id: op.opId, record_type: op.recordType, operation: op.operation,
      base_version: op.baseVersion, payload: op.payload,
    })) });
    const results = (data.data.results || []) as PushResult[];
    for (const result of results) {
      const op = ops.find((entry) => entry.opId === result.op_id);
      if (!op) continue;
      if (result.status === "synced") {
        await offlineDb.outbox.update(op.opId, { status: "synced", error: undefined });
        if (op.recordType === "ticket" && result.result) {
          const ticket = result.result as Ticket;
          await offlineDb.records.put({ userId, workspaceId, kind: "ticket", recordId: ticket.id,
            version: ticket.version, deleted: false, updatedAt: ticket.updated_at, payload: ticket });
        }
      } else if (result.status === "conflict" && result.server) {
        const changes = result.local || {};
        if (mergeNonConflicting(op, result.server, changes)) {
          hasAutoMerge = true;
          await offlineDb.outbox.update(op.opId, { ...op, payload: { id: result.server.id, changes }, status: "pending" });
        } else {
          await offlineDb.outbox.update(op.opId, { status: "conflict", conflictServer: result.server,
            error: "The same field changed on the server and this device." });
        }
      } else {
        const attempts = (op.attempts || 0) + 1;
        const retryDelay = Math.min(300000, 1000 * 2 ** Math.min(attempts, 8)) * (0.75 + Math.random() * 0.5);
        await offlineDb.outbox.update(op.opId, { status: "failed", attempts,
          nextAttemptAt: new Date(Date.now() + retryDelay).toISOString(), error: result.error || "Sync failed." });
      }
    }
    await pullChanges(userId, workspaceId);
  } catch (error) {
    for (const op of ops) {
      const attempts = (op.attempts || 0) + 1;
      const delay = Math.min(300000, 1000 * 2 ** Math.min(attempts, 8)) * (0.75 + Math.random() * 0.5);
      await offlineDb.outbox.update(op.opId, { status: "failed", attempts,
        nextAttemptAt: new Date(Date.now() + delay).toISOString(), error: error instanceof Error ? error.message : "Sync failed." });
    }
  }
  signalSyncChanged();
  if (hasAutoMerge) await runSync(userId, workspaceId);
}

export function syncWorkspace(userId: string, workspaceId: string): Promise<void> {
  const previous = activeSyncs.get(userId);
  const execute = async () => {
    if (locks) await locks.request(`pika-sync-${userId}`, async () => { await runSync(userId, workspaceId); });
    else await runSync(userId, workspaceId);
  };
  let task: Promise<void>;
  task = (previous ? previous.catch(() => undefined).then(execute) : execute()).finally(() => {
    if (activeSyncs.get(userId) === task) activeSyncs.delete(userId);
    signalSyncChanged();
  });
  activeSyncs.set(userId, task);
  return task;
}

export async function resolveSyncConflict(opId: string, choice: "server" | "local", userId: string) {
  const op = await offlineDb.outbox.get(opId);
  if (!op) return;
  if (choice === "server") {
    const server = op.conflictServer as Ticket | undefined;
    if (server) {
      await offlineDb.records.put({ userId, workspaceId: op.workspaceId, kind: "ticket", recordId: server.id,
        version: server.version, deleted: false, updatedAt: server.updated_at, payload: server });
      const detail = await offlineDb.records.get([userId, op.workspaceId, "ticket-detail", server.id]);
      if (detail) await offlineDb.records.put({ ...detail, version: server.version, payload: { ...(detail.payload as Ticket), ...server } });
    }
    await offlineDb.outbox.delete(opId);
  } else {
    const payload = op.payload as { id: string; changes: Record<string, unknown> };
    const server = op.conflictServer as Ticket | undefined;
    if (server) {
      const merged = { ...server, ...payload.changes };
      await offlineDb.records.put({ userId, workspaceId: op.workspaceId, kind: "ticket", recordId: server.id,
        version: server.version, deleted: false, updatedAt: new Date().toISOString(), payload: merged });
      const detail = await offlineDb.records.get([userId, op.workspaceId, "ticket-detail", server.id]);
      if (detail) await offlineDb.records.put({ ...detail, version: server.version, payload: { ...(detail.payload as Ticket), ...merged } });
      await offlineDb.outbox.update(opId, { status: "pending", baseVersion: server.version,
        baseSnapshot: server as unknown as Record<string, unknown>, conflictServer: undefined, error: undefined });
    }
  }
  signalSyncChanged();
  void syncWorkspace(userId, op.workspaceId).catch(() => undefined);
}
