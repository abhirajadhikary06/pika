import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, getErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AcceptInvitationPage() {
  const { token } = useParams<{ token: string }>();
  const { refreshUser, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    if (isLoading || !isAuthenticated) return;
    if (!token) {
      setError("This invitation link is invalid.");
      return;
    }
    api.post(`/invitations/${token}/accept`)
      .then(async () => {
        await refreshUser();
        navigate("/workspace", { replace: true });
      })
      .catch((err) => setError(getErrorMessage(err)));
  }, [isAuthenticated, isLoading, navigate, refreshUser, token]);

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center">Loading…</div>;
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="card w-full max-w-md p-6 text-center">
          <h1 className="text-xl font-semibold text-slate-900">You’re invited to Pika</h1>
          <p className="mt-2 text-sm text-slate-600">
            Sign in with the invited email address to accept this workspace invitation.
          </p>
          <Link to={`/login?redirect=${encodeURIComponent(`/invite/${token}`)}`} className="btn-primary mt-5">
            Sign in to accept
          </Link>
        </div>
      </div>
    );
  }

  if (!error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-brand-600 border-t-transparent" />
          <p className="mt-4 text-sm text-slate-600">Accepting your invitation…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="card w-full max-w-md p-6 text-center">
        <h1 className="text-xl font-semibold text-slate-900">Unable to accept invitation</h1>
        <p className="mt-2 text-sm text-red-600">{error}</p>
        <Link to="/" className="btn-primary mt-5">Return to Pika</Link>
      </div>
    </div>
  );
}
