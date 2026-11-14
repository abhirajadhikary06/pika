import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { api, getErrorMessage, isNetworkUnavailable } from "./api";
import {
  cacheOfflineSession,
  clearAccountData,
  countPendingOperations,
  getOfflineSession,
  requestPersistentStorage,
} from "./offlineDb";
import type { User } from "@/types";

const LAST_USER_ID_KEY = "pika_last_user_id";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isOffline: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<boolean>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function isRejectedSession(error: unknown): boolean {
  return (
    axios.isAxiosError(error) &&
    (error.response?.status === 401 || error.response?.status === 403)
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);

  const refreshUser = useCallback(async () => {
    const token = localStorage.getItem("pika_access_token");
    if (!token) {
      setUser(null);
      setIsOffline(false);
      setIsLoading(false);
      return;
    }

    try {
      const { data } = await api.get("/auth/me");
      const currentUser = data.data as User;
      localStorage.setItem(LAST_USER_ID_KEY, currentUser.id);
      localStorage.removeItem("pika_workspace_id");
      setUser(currentUser);
      setIsOffline(false);
      void cacheOfflineSession(currentUser).catch(() => undefined);
      void requestPersistentStorage();
    } catch (error) {
      if (isRejectedSession(error)) {
        localStorage.removeItem("pika_access_token");
        localStorage.removeItem("pika_refresh_token");
        localStorage.removeItem(LAST_USER_ID_KEY);
        setUser(null);
        setIsOffline(false);
        queryClient.clear();
      } else if (isNetworkUnavailable(error)) {
        const savedUserId = localStorage.getItem(LAST_USER_ID_KEY);
        const savedUser = savedUserId
          ? await getOfflineSession(savedUserId).catch(() => undefined)
          : undefined;
        setUser(savedUser || null);
        setIsOffline(!!savedUser);
      } else {
        setUser(null);
        setIsOffline(false);
      }
    } finally {
      setIsLoading(false);
    }
  }, [queryClient]);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    const onNetworkUnavailable = () => setIsOffline(true);
    const onNetworkAvailable = () => setIsOffline(false);
    const onAuthExpired = () => {
      localStorage.removeItem(LAST_USER_ID_KEY);
      setUser(null);
      setIsOffline(false);
      queryClient.clear();
    };

    window.addEventListener("pika:network-unavailable", onNetworkUnavailable);
    window.addEventListener("pika:network-available", onNetworkAvailable);
    window.addEventListener("pika:auth-expired", onAuthExpired);
    return () => {
      window.removeEventListener("pika:network-unavailable", onNetworkUnavailable);
      window.removeEventListener("pika:network-available", onNetworkAvailable);
      window.removeEventListener("pika:auth-expired", onAuthExpired);
    };
  }, [queryClient]);

  const login = async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email, password });
    const currentUser = data.data.user as User;
    queryClient.clear();
    localStorage.setItem("pika_access_token", data.data.access_token);
    localStorage.setItem("pika_refresh_token", data.data.refresh_token);
    localStorage.setItem(LAST_USER_ID_KEY, currentUser.id);
    localStorage.removeItem("pika_workspace_id");
    setUser(currentUser);
    setIsOffline(false);
    setIsLoading(false);
    void cacheOfflineSession(currentUser).catch(() => undefined);
    void requestPersistentStorage();
  };

  const register = async (email: string, password: string, fullName: string) => {
    await api.post("/auth/register", { email, password, full_name: fullName });
    await login(email, password);
  };

  const logout = async (): Promise<boolean> => {
    const currentUserId = user?.id;
    if (currentUserId) {
      const pendingCount = await countPendingOperations(currentUserId).catch(() => 0);
      if (
        pendingCount > 0 &&
        !window.confirm(
          "You have " + pendingCount +
            " unsynced change(s). Signing out will delete them and this account's saved offline data. Continue?",
        )
      ) {
        return false;
      }
    }

    const refreshToken = localStorage.getItem("pika_refresh_token");
    try {
      if (refreshToken && !isOffline) {
        await api.post("/auth/logout", {}, {
          headers: { Authorization: "Bearer " + refreshToken },
        });
      }
    } catch {
      // A network failure must not keep the user signed in on this device.
    }

    if (currentUserId) {
      await clearAccountData(currentUserId).catch(() => undefined);
      localStorage.removeItem("pika_workspace_id:" + currentUserId);
    }
    localStorage.removeItem("pika_access_token");
    localStorage.removeItem("pika_refresh_token");
    localStorage.removeItem(LAST_USER_ID_KEY);
    localStorage.removeItem("pika_workspace_id");
    queryClient.clear();
    setUser(null);
    setIsOffline(false);
    return true;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isOffline,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export { getErrorMessage };
