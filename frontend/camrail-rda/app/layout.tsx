import type { Metadata } from "next";
import "@fontsource-variable/inter";
import AppShell from "@/components/AppShell";
import "./globals.css";
import { LanguageProvider } from "@/lib/LanguageContext";

export const metadata: Metadata = {
  title: "CAMRAIL RailMind Lite",
  description: "Système souverain d'interrogation documentaire ferroviaire intelligent - CAMRAIL",
  icons: {
    icon: "/favicon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className="h-full bg-slate-50">
      <body className="h-full text-slate-900 antialiased selection:bg-red-100 selection:text-red-900">
        <LanguageProvider>
          <AppShell>{children}</AppShell>
        </LanguageProvider>
      </body>
    </html>
  );
}
