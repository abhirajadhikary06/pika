import Dexie, { type Table } from "dexie";
import type { User } from "@/types";

export const ACCOUNT_SCOPE = "__account__";

export type OfflineRecordKind = "workspace" | "ticket" | "ticket-detail";

export interface CachedRecord<T = unknown> {
  userId: string;
  workspaceId: string;
  kind: OfflineRecordKind;
  recordId: string;
  version: number;
  deleted: boolean;
  updatedAt: string;
  payload: T;
}

export interface OutboxOperation {
  opId: string;
  userId: string;
  workspaceId: string;
  recordId: string;
  recordType: "ticket" | "comment";
  operation: "create" | "update" | "delete";
  payload: unknown;
  createdAt: string;
  status: "pending" | "inflight" | "conflict";
}

export interface SyncMetadata {
  userId: string;
  workspaceId: string;
  key: string;
  value: unknown;
  updatedAt: string;
}

class PikaOfflineDatabase extends Dexie {
  records!: Table<CachedRecord, [string, string, string, string]>;
  outbox!: Table<OutboxOperation, string>;
  meta!: Table<SyncMetadata, [string, string, string]>;

  constructor() {
    super("pika-offline");
    this.version(1).stores({
      records: "&[userId+workspaceId+kind+recordId],[userId+workspaceId+kind],[userId+workspaceId],userId",
      outbox: "&opId,[userId+workspaceId],[userId+status],userId,createdAt",
      meta: "&[userId+workspaceId+key],[userId+workspaceId],userId",
    });
  }
}

export const offlineDb = new PikaOfflineDatabase();

export class OfflineStorageQuotaError extends Error {
  constructor() {
    super("Device storage is full. Pika could not save this data for offline use.");
    this.name = "OfflineStorageQuotaError";
  }
}

export function isOfflineStorageAvailable(): boolean {
  return typeof indexedDB !== "undefined";
}

function isQuotaExceeded(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    ["QuotaExceededError", "NS_ERROR_DOM_QUOTA_REACHED"].includes(String(error.name))
  );
}

async function withQuotaHandling<T>(write: () => Promise<T>): Promise<T> {
  try {
    return await write();
  } catch (error) {
    if (!isQuotaExceeded(error)) throw error;
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("pika:storage-quota"));
    }
    throw new OfflineStorageQuotaError();
  }
}

export async function cacheRecords<T extends { id: string; version?: number }>(
  userId: string,
  workspaceId: string,
  kind: OfflineRecordKind,
  records: T[],
): Promise<void> {
  if (!isOfflineStorageAvailable()) return;
  const updatedAt = new Date().toISOString();
  await withQuotaHandling(() =>
    offlineDb.records.bulkPut(
      records.map((payload) => ({
        userId,
        workspaceId,
        kind,
        recordId: payload.id,
        version: payload.version ?? 1,
        deleted: false,
        updatedAt,
        payload,
      })),
    ),
  );
}

export async function replaceCachedRecords<T extends { id: string; version?: number }>(
  userId: string,
  workspaceId: string,
  kind: OfflineRecordKind,
  records: T[],
): Promise<void> {
  if (!isOfflineStorageAvailable()) return;
  const updatedAt = new Date().toISOString();
  await withQuotaHandling(() =>
    offlineDb.transaction("rw", offlineDb.records, async () => {
      await offlineDb.records
        .where("[userId+workspaceId+kind]")
        .equals([userId, workspaceId, kind])
        .delete();
      await offlineDb.records.bulkPut(
        records.map((payload) => ({
          userId,
          workspaceId,
          kind,
          recordId: payload.id,
          version: payload.version ?? 1,
          deleted: false,
          updatedAt,
          payload,
        })),
      );
    }),
  );
}

export async function getCachedRecords<T>(
  userId: string,
  workspaceId: string,
  kind: OfflineRecordKind,
): Promise<T[]> {
  if (!isOfflineStorageAvailable()) return [];
  const records = await offlineDb.records
    .where("[userId+workspaceId+kind]")
    .equals([userId, workspaceId, kind])
    .toArray();
  return records.filter((record) => !record.deleted).map((record) => record.payload as T);
}

export async function getCachedRecord<T>(
  userId: string,
  workspaceId: string,
  kind: OfflineRecordKind,
  recordId: string,
): Promise<T | undefined> {
  if (!isOfflineStorageAvailable()) return undefined;
  const record = await offlineDb.records.get([userId, workspaceId, kind, recordId]);
  return record && !record.deleted ? (record.payload as T) : undefined;
}

export async function cacheOfflineSession(user: User): Promise<void> {
  if (!isOfflineStorageAvailable()) return;
  await withQuotaHandling(() =>
    offlineDb.meta.put({
      userId: user.id,
      workspaceId: ACCOUNT_SCOPE,
      key: "offline-session",
      value: user,
      updatedAt: new Date().toISOString(),
    }),
  );
}

export async function getOfflineSession(userId: string): Promise<User | undefined> {
  if (!isOfflineStorageAvailable()) return undefined;
  const session = await offlineDb.meta.get([userId, ACCOUNT_SCOPE, "offline-session"]);
  return session?.value as User | undefined;
}

export async function countPendingOperations(userId: string): Promise<number> {
  if (!isOfflineStorageAvailable()) return 0;
  return offlineDb.outbox.where("userId").equals(userId).count();
}

export async function clearAccountData(userId: string): Promise<void> {
  if (!isOfflineStorageAvailable()) return;
  await offlineDb.transaction("rw", offlineDb.records, offlineDb.outbox, offlineDb.meta, async () => {
    await offlineDb.records.where("userId").equals(userId).delete();
    await offlineDb.outbox.where("userId").equals(userId).delete();
    await offlineDb.meta.where("userId").equals(userId).delete();
  });
}

export async function requestPersistentStorage(): Promise<boolean> {
  if (typeof navigator === "undefined" || !navigator.storage) return false;
  const storage = navigator.storage as StorageManager & { persist?: () => Promise<boolean> };
  if (typeof storage.persist !== "function") return false;
  try {
    return await storage.persist();
  } catch {
    return false;
  }
}
