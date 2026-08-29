"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/auth";
import { useLanguage } from "@/lib/LanguageContext";

export default function LoginPage() {
  const router = useRouter();
  const { language, setLanguage, t } = useLanguage();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (loading) {
      return;
    }

    setError("");
    setLoading(true);

    try {
      await login(username, password);
      router.push("/assistant");
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : t("login.error"),
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-10 relative">
      <div className="w-full max-w-md">
        {/* Logo & Header */}
        <div className="flex flex-col items-center justify-center gap-3 w-full mb-8">
          <img 
            src="/camrail-logo.png" 
            alt="CAMRAIL Logo" 
            className="h-16 w-auto object-contain"
          />
          <div className="text-center">
            <p className="text-xl font-bold text-slate-900 leading-tight">{t("login.title")}</p>
            <p className="text-sm font-medium text-slate-500 uppercase tracking-widest mt-1">
              {t("login.subtitle")}
            </p>
          </div>
        </div>

        {/* Login card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/40 sm:p-8 relative overflow-hidden">
          {/* Subtle top border accent */}
          <div className="absolute top-0 left-0 w-full h-1 bg-camrail-red"></div>
          
          {/* Language Selector (Inside Card) */}
          <div className="absolute top-4 right-4 flex bg-slate-50 rounded-full p-0.5 shadow-sm border border-slate-200">
            <button
              onClick={() => setLanguage('fr')}
              className={`px-2.5 py-1 text-[10px] font-bold rounded-full transition ${language === 'fr' ? 'bg-camrail-red text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}
            >
              FR
            </button>
            <button
              onClick={() => setLanguage('en')}
              className={`px-2.5 py-1 text-[10px] font-bold rounded-full transition ${language === 'en' ? 'bg-camrail-red text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}
            >
              EN
            </button>
          </div>

          <h2 className="text-xl font-bold text-slate-900 mt-2">
            {language === 'fr' ? 'Connexion' : 'Login'}
          </h2>
          <p className="mt-1 text-sm text-slate-500 mb-6 pr-12">
            {language === 'fr' ? 'Utilisez vos identifiants d\'entreprise CAMRAIL.' : 'Use your CAMRAIL corporate credentials.'}
          </p>

          {/* Microsoft SSO Button */}
          <div className="mb-6">
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/auth/login/microsoft`}
              className="flex w-full items-center justify-center gap-3 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:border-slate-400 hover:shadow focus:outline-none focus:ring-2 focus:ring-camrail-red focus:ring-offset-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" className="h-5 w-5">
                <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
                <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
                <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
                <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
              </svg>
              {language === 'fr' ? 'Se connecter avec Microsoft' : 'Sign in with Microsoft'}
            </a>
          </div>

          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-white px-4 text-slate-400">
                {language === 'fr' ? 'Ou connexion locale (Admin)' : 'Or local login (Admin)'}
              </span>
            </div>
          </div>

          {error && (
            <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 flex items-start gap-3">
              <svg className="w-5 h-5 text-red-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm font-medium text-red-700">
                {error}
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-5">
            {/* Email */}
            <div>
              <label
                htmlFor="username"
                className="mb-2 block text-sm font-semibold text-slate-700"
              >
                {t("login.email")}
              </label>

              <input
                id="username"
                type="email"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="prenom.nom@camrail.net"
                autoComplete="email"
                required
                disabled={loading}
                className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-camrail-red focus:ring-1 focus:ring-camrail-red disabled:cursor-not-allowed disabled:bg-slate-50 disabled:opacity-60"
              />
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="mb-2 block text-sm font-semibold text-slate-700"
              >
                {t("login.password")}
              </label>

              <input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
                disabled={loading}
                className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-camrail-red focus:ring-1 focus:ring-camrail-red disabled:cursor-not-allowed disabled:bg-slate-50 disabled:opacity-60"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !username.trim() || !password}
              className="w-full mt-2 rounded-xl bg-camrail-red px-5 py-3.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-red-700 hover:shadow-md disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
            >
              {loading ? (language === 'fr' ? "Vérification en cours..." : "Verifying...") : t("login.button")}
            </button>
          </form>
        </div>

        <div className="mt-8 text-center text-xs text-slate-400 flex flex-col gap-1">
          <p>© {new Date().getFullYear()} CAMRAIL</p>
          <p>Propulsé par la technologie d'Intelligence Artificielle</p>
        </div>
      </div>
    </main>
  );
}