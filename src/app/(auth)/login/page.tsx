'use client';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { LoginRequestSchema, type LoginRequest } from '@/lib/schemas/auth';

export default function LoginPage() {
  const router = useRouter();
  const [authError, setAuthError] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<LoginRequest>({ resolver: zodResolver(LoginRequestSchema) });

  async function onSubmit(data: LoginRequest) {
    setAuthError(null);
    const result = await signIn('credentials', {
      email:    data.email,
      password: data.password,
      redirect: false,
    });
    if (result?.error) {
      setAuthError('Invalid email or password. Try admin@forge.dev with any 8+ char password.');
      return;
    }
    router.replace('/runs');
  }

  return (
    <div className="login-page">
      <div className="login-card">
        {/* Inline SVG logo */}
        <svg className="login-logo" viewBox="0 0 40 40" fill="none"
             aria-label="Forge-OH" width="40" height="40">
          <rect width="40" height="40" rx="8" fill="var(--color-primary)" />
          <path d="M10 28 L20 12 L30 28" stroke="white" strokeWidth="3"
                strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <circle cx="20" cy="28" r="2.5" fill="white" />
        </svg>

        <h1 className="login-title">Sign in to Forge-OH</h1>

        {authError && (
          <div className="auth-error" role="alert" aria-live="assertive">
            {authError}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="form-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              aria-describedby={errors.email ? 'email-error' : undefined}
              aria-invalid={!!errors.email}
              {...register('email')}
            />
            {errors.email && (
              <span id="email-error" className="field-error" role="alert">
                {errors.email.message}
              </span>
            )}
          </div>

          <div className="form-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              aria-describedby={errors.password ? 'password-error' : undefined}
              aria-invalid={!!errors.password}
              {...register('password')}
            />
            {errors.password && (
              <span id="password-error" className="field-error" role="alert">
                {errors.password.message}
              </span>
            )}
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="login-hint">
          Demo: <code>admin@forge.dev</code> / <code>password123</code>
        </p>
      </div>
    </div>
  );
}
