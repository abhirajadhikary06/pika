import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth, getErrorMessage } from "@/lib/auth";
import { api } from "@/lib/api";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

const schema = z.object({
  full_name: z.string().min(2),
});

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const qc = useQueryClient();

  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { full_name: user?.full_name || "" },
  });

  const onSubmit = async (data: { full_name: string }) => {
    setError("");
    setMessage("");
    try {
      await api.patch("/auth/me", data);
      await refreshUser();
      qc.invalidateQueries();
      setMessage("Profile updated.");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500">Manage your account.</p>
      </div>

      <div className="card p-6">
        <h2 className="mb-4 font-semibold">Profile</h2>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {message && <p className="text-sm text-emerald-600">{message}</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div>
            <label className="label">Email</label>
            <input className="input bg-slate-50" value={user?.email || ""} disabled />
          </div>
          <div>
            <label className="label">Full name</label>
            <input className="input" {...register("full_name")} />
          </div>
          <button type="submit" className="btn-primary" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Save changes"}
          </button>
        </form>
      </div>
    </div>
  );
}
