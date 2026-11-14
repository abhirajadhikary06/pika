import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Ticket,
  Settings,
  Bell,
  LogOut,
  Building2,
  Menu,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useQuery } from "@tanstack/react-query";
import { api, isNetworkUnavailable } from "@/lib/api";
import { ACCOUNT_SCOPE, getCachedRecords, replaceCachedRecords } from "@/lib/offlineDb";
import { syncWorkspace } from "@/lib/sync";
import type { Workspace } from "@/types";
import { cn } from "@/lib/utils";
import logo from "@/assets/logo-128.png";

const nav = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/tickets", icon: Ticket, label: "Tickets" },
  { to: "/notifications", icon: Bell, label: "Notifications" },
  { to: "/workspace", icon: Building2, label: "Workspace" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces", user?.id],
    queryFn: async () => {
      try {
        const { data } = await api.get("/workspaces");
        const workspaces = data.data as Workspace[];
        if (user) {
          await replaceCachedRecords(user.id, ACCOUNT_SCOPE, "workspace", workspaces).catch(() => undefined);
        }
        return workspaces;
      } catch (error) {
        if (!user || !isNetworkUnavailable(error)) throw error;
        return getCachedRecords<Workspace>(user.id, ACCOUNT_SCOPE, "workspace");
      }
    },
    enabled: !!user,
  });

  const { data: unreadCount = 0 } = useQuery({
    queryKey: ["notifications", user?.id, "unread-count"],
    queryFn: async () => {
      const { data } = await api.get("/notifications", { params: { per_page: 1 } });
      return (data.meta?.unread_count ?? 0) as number;
    },
    refetchInterval: 30000,
  });

  const workspaceSelectionKey = user ? "pika_workspace_id:" + user.id : "pika_workspace_id";
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(
    () => localStorage.getItem(workspaceSelectionKey) || ""
  );
  const currentWs = workspaces?.find((ws) => ws.id === selectedWorkspaceId) || workspaces?.[0];

  useEffect(() => {
    if (!user || !currentWs) return;
    const sync = () => { void syncWorkspace(user.id, currentWs.id).catch(() => undefined); };
    const onVisible = () => { if (document.visibilityState === "visible") sync(); };
    sync();
    window.addEventListener("online", sync);
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(sync, 30000);
    return () => {
      window.removeEventListener("online", sync);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [user, currentWs?.id]);

  useEffect(() => {
    if (currentWs && currentWs.id !== selectedWorkspaceId) {
      setSelectedWorkspaceId(currentWs.id);
      localStorage.setItem(workspaceSelectionKey, currentWs.id);
    }
  }, [currentWs, selectedWorkspaceId, workspaceSelectionKey]);

  const handleLogout = async () => {
    const didLogout = await logout();
    if (didLogout) navigate("/login");
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-5">
          <img src={logo} alt="Pika" className="h-8 w-8 rounded-lg" />
          <span className="text-lg font-semibold tracking-tight text-slate-900">Pika</span>
          <button
            className="ml-auto rounded-lg p-1 text-slate-500 hover:bg-slate-100 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {workspaces && workspaces.length > 0 && currentWs && (
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="truncate text-xs font-medium uppercase tracking-wider text-slate-400">
              Workspaces
            </p>
            <select
              className="mt-1 w-full truncate rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm font-medium text-slate-800 focus:border-brand-500 focus:outline-none"
              value={currentWs.id}
              onChange={(event) => {
                setSelectedWorkspaceId(event.target.value);
                localStorage.setItem(workspaceSelectionKey, event.target.value);
              }}
              aria-label="Select workspace"
            >
              {workspaces.map((ws) => <option key={ws.id} value={ws.id}>{ws.name}</option>)}
            </select>
          </div>
        )}

        <nav className="flex-1 space-y-1 p-3">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                )
              }
            >
              <span className="relative shrink-0">
                <item.icon className="h-5 w-5" />
                {item.to === "/notifications" && unreadCount > 0 && (
                  <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-red-500" aria-label="Unread notifications" />
                )}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-4">
          <div className="mb-3 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
              {user?.full_name?.charAt(0)?.toUpperCase() || "U"}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-900">{user?.full_name}</p>
              <p className="truncate text-xs text-slate-500">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col min-w-0">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/80 px-4 backdrop-blur lg:px-6">
          <button
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
        </header>
        <main className="flex-1 p-4 lg:p-6">
          <Outlet context={{ workspace: currentWs }} />
        </main>
      </div>
    </div>
  );
}
