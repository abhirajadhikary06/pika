import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, getErrorMessage } from "./api";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const token = localStorage.getItem("pika_access_token");
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data.data);
    } catch {
      setUser(null);
      localStorage.removeItem("pika_access_token");
      localStorage.removeItem("pika_refresh_token");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("pika_access_token", data.data.access_token);
    localStorage.setItem("pika_refresh_token", data.data.refresh_token);
    setUser(data.data.user);
  };

  const register = async (email: string, password: string, fullName: string) => {
    await api.post("/auth/register", { email, password, full_name: fullName });
    await login(email, password);
  };

  const logout = async () => {
    const refresh = localStorage.getItem("pika_refresh_token");
    try {
      if (refresh) {
        await api.post("/auth/logout", {}, {
          headers: { Authorization: `Bearer ${refresh}` },
        });
      }
    } catch {
      // ignore
    }
    localStorage.removeItem("pika_access_token");
    localStorage.removeItem("pika_refresh_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
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
