import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";
const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
let apiOrigin = "";
try {
  if (apiUrl.startsWith("http://") || apiUrl.startsWith("https://")) {
    apiOrigin = new URL(apiUrl).origin;
  }
} catch {
  apiOrigin = "";
}

/**
 * LIMITE CONNUE DE SÉCURITÉ (CSP Script-src) :
 * L'inclusion de 'unsafe-inline' dans script-src est un compromis technique avec le runtime
 * de Next.js (hydratation client et scripts inline de démarrage). Une politique CSP stricte
 * avec nonce cryptographique par requête ('nonce-...') serait plus protectrice mais exigerait
 * un middleware Next.js dynamique réécrivant les balises HTML et les en-têtes à chaque requête.
 * En développement, 'unsafe-eval' est également ajouté car requis par les source maps et le HMR de Next.js.
 */
const scriptSrc = isDev
  ? "'self' 'unsafe-inline' 'unsafe-eval'"
  : "'self' 'unsafe-inline'";

const connectSources = ["'self'"];
if (apiOrigin) {
  connectSources.push(apiOrigin);
}
if (isDev) {
  if (!connectSources.includes("http://localhost:8000")) connectSources.push("http://localhost:8000");
  if (!connectSources.includes("http://127.0.0.1:8000")) connectSources.push("http://127.0.0.1:8000");
}

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src ${scriptSrc}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src ${connectSources.join(" ")}`,
  "frame-src 'self' blob:",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: contentSecurityPolicy,
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "no-referrer",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
