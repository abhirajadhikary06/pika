import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate } from "react-router-dom";
import { useAuth, getErrorMessage } from "@/lib/auth";
import { useState } from "react";
import logo from "@/assets/logo-256.png";

const schema = z
  .object({
    full_name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Invalid email"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: doRegister } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setError("");
    try {
      await doRegister(data.email, data.password, data.full_name);
      navigate("/");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center gap-3">
          <img src={logo} alt="Pika" className="h-10 w-10 rounded-xl" />
          <span className="text-2xl font-bold text-slate-900">Pika</span>
        </div>
        <h1 className="text-2xl font-semibold text-slate-900">Create your account</h1>
        <p className="mt-1 text-sm text-slate-500">Start managing support tickets in minutes.</p>

        <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          )}
          <div>
            <label className="label">Full name</label>
            <input className="input" {...register("full_name")} />
            {errors.full_name && (
              <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>
            )}
          </div>
          <div>
            <label className="label">Email</label>
            <input type="email" className="input" {...register("email")} />
            {errors.email && (
              <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
            )}
          </div>
          <div>
            <label className="label">Password</label>
            <input type="password" className="input" {...register("password")} />
            {errors.password && (
              <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
            )}
          </div>
          <div>
            <label className="label">Confirm password</label>
            <input type="password" className="input" {...register("confirm")} />
            {errors.confirm && (
              <p className="mt-1 text-xs text-red-600">{errors.confirm.message}</p>
            )}
          </div>
          <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
