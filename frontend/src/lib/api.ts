import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

function dispatchBrowserEvent(name: string) {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(name));
}

function clearTokens() {
  localStorage.removeItem("pika_access_token");
  localStorage.removeItem("pika_refresh_token");
}

export function isNetworkUnavailable(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false;
  return !error.response || error.response.status >= 500;
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem("pika_access_token");
  if (token && config.headers && !config.headers.Authorization) {
    config.headers.Authorization = "Bearer " + token;
  }
  return config;
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string | null) => void;
  reject: (err: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((pending) => {
    if (error) pending.reject(error);
    else pending.resolve(token);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => {
    dispatchBrowserEvent("pika:network-available");
    return response;
  },
  async (error: AxiosError) => {
    if (!error.response || error.response.status >= 500) {
      dispatchBrowserEvent("pika:network-unavailable");
    }

    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const authEndpoint = /\/auth\/(login|register|refresh|logout)$/.test(original?.url || "");
    if (error.response?.status !== 401 || !original || original._retry || authEndpoint) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then((token) => {
        if (original.headers) original.headers.Authorization = "Bearer " + token;
        return api(original);
      });
    }

    original._retry = true;
    isRefreshing = true;
    const refreshToken = localStorage.getItem("pika_refresh_token");
    if (!refreshToken) {
      processQueue(error, null);
      clearTokens();
      dispatchBrowserEvent("pika:auth-expired");
      isRefreshing = false;
      return Promise.reject(error);
    }

    try {
      const { data } = await axios.post(API_BASE + "/auth/refresh", {}, {
        headers: { Authorization: "Bearer " + refreshToken },
        timeout: 30000,
      });
      const newToken = data.data.access_token;
      localStorage.setItem("pika_access_token", newToken);
      processQueue(null, newToken);
      if (original.headers) original.headers.Authorization = "Bearer " + newToken;
      return api(original);
    } catch (refreshError) {
      processQueue(refreshError, null);
      const refreshWasRejected =
        axios.isAxiosError(refreshError) &&
        !!refreshError.response &&
        refreshError.response.status < 500;
      if (refreshWasRejected) {
        clearTokens();
        dispatchBrowserEvent("pika:auth-expired");
      } else {
        dispatchBrowserEvent("pika:network-unavailable");
      }
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    return err.response?.data?.error?.message || err.message || "Request failed";
  }
  if (err instanceof Error) return err.message;
  return "An unexpected error occurred";
}
