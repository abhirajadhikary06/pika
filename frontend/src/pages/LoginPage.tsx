import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth, getErrorMessage } from "@/lib/auth";
import { useState } from "react";
import logo from "@/assets/logo-256.png";

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(1, "Password is required"),
});

type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setError("");
    try {
      await login(data.email, data.password);
      const redirect = new URLSearchParams(location.search).get("redirect");
      navigate(redirect || "/");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <div className="flex min-h-screen">
      <div className="flex flex-1 flex-col justify-center px-6 py-12 lg:px-12">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3">
            <img src={logo} alt="Pika" className="h-10 w-10 rounded-xl" />
            <span className="text-2xl font-bold text-slate-900">Pika</span>
          </div>
          <h1 className="text-2xl font-semibold text-slate-900">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">
            Welcome back. Enter your credentials to continue.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-5">
            {error && (
              <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
            )}
            <div>
              <label className="label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className="input"
                {...register("email")}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
              )}
            </div>
            <div>
              <label className="label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="input"
                {...register("password")}
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
              )}
            </div>
            <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
              {isSubmitting ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Don't have an account?{" "}
            <Link to="/register" className="font-medium text-brand-600 hover:text-brand-700">
              Create one
            </Link>
          </p>
        </div>
      </div>
      <div className="hidden bg-gradient-to-br from-brand-600 to-brand-900 lg:flex lg:w-1/2 items-center justify-center p-12">
        <div className="max-w-md text-white">
          <h2 className="text-3xl font-bold leading-tight">
            Modern helpdesk for focused teams
          </h2>
          <p className="mt-4 text-brand-100">
            Track tickets, collaborate with your team, and deliver great support — all in one place.
          </p>
        </div>
      </div>
    </div>
  );
}
