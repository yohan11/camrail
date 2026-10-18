"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/auth";
import { useLanguage } from "@/lib/LanguageContext";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const { language, setLanguage, t } = useLanguage();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ssoEnabled = process.env.NEXT_PUBLIC_MICROSOFT_SSO_ENABLED === "true";

  function mapErrorMessage(rawErr: string): string {
    const lower = rawErr.toLowerCase();
    if (
      lower.includes("trop de tentatives") ||
      lower.includes("too many requests") ||
      lower.includes("429") ||
      lower.includes("réessayez dans")
    ) {
      return rawErr;
    }
    if (
      lower.includes("credential") ||
      lower.includes("incorrect") ||
      lower.includes("invalid") ||
      lower.includes("401") ||
      lower.includes("unauthorized") ||
      lower.includes("identifiant")
    ) {
      return language === "fr"
        ? "Identifiant ou mot de passe incorrect. Vérifiez vos informations."
        : "Incorrect username or password. Please verify your credentials.";
    }
    if (
      lower.includes("disabled") ||
      lower.includes("désactivé") ||
      lower.includes("inactive") ||
      lower.includes("inactif")
    ) {
      return language === "fr"
        ? "Ce compte est désactivé. Contactez l'administrateur CAMRAIL."
        : "This account is disabled. Contact your CAMRAIL administrator.";
    }
    if (
      lower.includes("fetch") ||
      lower.includes("network") ||
      lower.includes("réseau") ||
      lower.includes("econnrefused") ||
      lower.includes("injoignable") ||
      lower.includes("failed to fetch")
    ) {
      return language === "fr"
        ? "Impossible de joindre le serveur CAMRAIL. Vérifiez votre connexion réseau."
        : "Cannot reach CAMRAIL server. Please verify your network connection.";
    }
    return rawErr || (language === "fr" ? "Erreur de connexion." : "Authentication error.");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (loading) return;

    setError("");
    setLoading(true);

    try {
      await login(username, password);
      router.push("/assistant");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(mapErrorMessage(msg));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-6 relative">
      <div className="w-full max-w-md">
        {/* En-tête compact */}
        <div className="flex flex-col items-center justify-center text-center mb-4">
          <img
            src="/camrail-logo-transparent.png"
            alt="CAMRAIL Logo"
            className="h-12 w-auto object-contain mb-2"
          />
          <h1 className="text-xl font-bold tracking-tight text-slate-900 leading-tight">
            CAMRAIL RailMind Lite
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-0.5">
            Portail souverain d&apos;intelligence documentaire ferroviaire
          </p>
        </div>

        {/* Carte de connexion compacte (hauteur totale < 600px) */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-lg shadow-slate-200/50 relative overflow-hidden">
          {/* Liseré haut CAMRAIL */}
          <div className="absolute top-0 left-0 w-full h-1 bg-camrail-red" />

          {/* Sélecteur de langue discret */}
          <div className="absolute top-4 right-4 flex bg-slate-100 rounded-full p-0.5 border border-slate-200">
            <button
              type="button"
              onClick={() => setLanguage("fr")}
              className={`px-2 py-0.5 text-[11px] font-bold rounded-full transition cursor-pointer ${
                language === "fr"
                  ? "bg-camrail-red text-white shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              FR
            </button>
            <button
              type="button"
              onClick={() => setLanguage("en")}
              className={`px-2 py-0.5 text-[11px] font-bold rounded-full transition cursor-pointer ${
                language === "en"
                  ? "bg-camrail-red text-white shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              EN
            </button>
          </div>

          <div className="mb-4">
            <h2 className="text-lg font-bold text-slate-900">
              {language === "fr" ? "Connexion" : "Login"}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {language === "fr"
                ? "Identifiants d'entreprise CAMRAIL."
                : "CAMRAIL corporate credentials."}
            </p>
          </div>

          {/* Bouton SSO Microsoft (conditionné par NEXT_PUBLIC_MICROSOFT_SSO_ENABLED) */}
          {ssoEnabled && (
            <div className="mb-4">
              <a
                href={`${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/+$/, "")}/auth/login/microsoft`}
                className="flex w-full items-center justify-center gap-2.5 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-2xs transition-all hover:bg-slate-50 hover:border-slate-400 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-camrail-red"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" className="h-4 w-4">
                  <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                  <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                  <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                  <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
                </svg>
                {language === "fr" ? "Se connecter avec Microsoft" : "Sign in with Microsoft"}
              </a>

              <div className="relative my-3">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-200"></div>
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-white px-2 text-slate-500">
                    {language === "fr" ? "Ou connexion locale" : "Or local login"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Alerte Erreur claire */}
          {error && (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 flex items-start gap-2.5">
              <svg className="w-4 h-4 text-red-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-xs font-medium text-red-700 leading-snug">
                {error}
              </p>
            </div>
          )}

          {/* Formulaire de connexion */}
          <form onSubmit={handleSubmit} className="space-y-3.5">
            {/* Email */}
            <div>
              <label
                htmlFor="username"
                className="mb-1 block text-xs font-semibold text-slate-700"
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
                className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 outline-hidden transition placeholder:text-slate-400 focus:border-camrail-red focus:ring-2 focus:ring-camrail-red/20 disabled:cursor-not-allowed disabled:bg-slate-50"
              />
            </div>

            {/* Mot de passe avec toggle Afficher / Masquer */}
            <div>
              <label
                htmlFor="password"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                {t("login.password")}
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                  disabled={loading}
                  className="w-full rounded-xl border border-slate-300 bg-white pl-3.5 pr-10 py-2 text-sm text-slate-900 outline-hidden transition placeholder:text-slate-400 focus:border-camrail-red focus:ring-2 focus:ring-camrail-red/20 disabled:cursor-not-allowed disabled:bg-slate-50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-700 focus-visible:outline-hidden focus-visible:text-camrail-red cursor-pointer"
                >
                  {showPassword ? (
                    // Eye slash icon
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"></path>
                      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"></path>
                      <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"></path>
                      <line x1="2" y1="2" x2="22" y2="22"></line>
                    </svg>
                  ) : (
                    // Eye icon
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Bouton de soumission */}
            <div className="pt-1">
              <Button
                type="submit"
                variant="primary"
                size="md"
                loading={loading}
                disabled={loading || !username.trim() || !password}
                className="w-full"
              >
                {loading
                  ? language === "fr"
                    ? "Vérification en cours..."
                    : "Verifying..."
                  : t("login.button")}
              </Button>
            </div>
          </form>
        </div>

        {/* Pied de page sobre */}
        <div className="mt-4 text-center text-[11px] text-slate-500">
          <p>© {new Date().getFullYear()} CAMRAIL • RailMind Lite</p>
        </div>
      </div>
    </main>
  );
}