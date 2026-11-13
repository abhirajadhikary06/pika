import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// Attach access token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem("pika_access_token");
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Refresh on 401
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string | null) => void;
  reject: (err: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((p) => {
    if (error) p.reject(error);
    else p.resolve(token);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          if (original.headers) original.headers.Authorization = `Bearer ${token}`;
          return api(original);
        });
      }
      original._retry = true;
      isRefreshing = true;
      const refresh = localStorage.getItem("pika_refresh_token");
      if (!refresh) {
        processQueue(error, null);
        localStorage.removeItem("pika_access_token");
        localStorage.removeItem("pika_refresh_token");
        window.location.href = "/login";
        return Promise.reject(error);
      }
      try {
        const { data } = await axios.post(`${API_BASE}/auth/refresh`, {}, {
          headers: { Authorization: `Bearer ${refresh}` },
        });
        const newToken = data.data.access_token;
        localStorage.setItem("pika_access_token", newToken);
        processQueue(null, newToken);
        if (original.headers) original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch (err) {
        processQueue(err, null);
        localStorage.removeItem("pika_access_token");
        localStorage.removeItem("pika_refresh_token");
        window.location.href = "/login";
        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    return err.response?.data?.error?.message || err.message || "Request failed";
  }
  if (err instanceof Error) return err.message;
  return "An unexpected error occurred";
}
