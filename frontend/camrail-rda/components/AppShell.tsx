"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { clearSession, getSession } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "@/lib/LanguageContext";

export default function AppShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { language, t } = useLanguage();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [session, setSession] = useState<ReturnType<typeof getSession>>(null);
  const [conversations, setConversations] = useState<{id: number, title: string}[]>([]);

  const loadConversations = () => {
    const currentSession = getSession();
    setSession(currentSession);
    
    if (currentSession) {
      apiFetch("/assistant/conversations")
        .then((data: any) => {
          if (Array.isArray(data)) {
            setConversations(data);
          }
        })
        .catch(console.error);
    }
  };

  useEffect(() => {
    loadConversations();

    const handleReload = () => {
      loadConversations();
    };

    window.addEventListener("reload-conversations", handleReload);
    return () => window.removeEventListener("reload-conversations", handleReload);
  }, [pathname]);

  function handleLogout() {
    clearSession();
    sessionStorage.removeItem("railmind_chat_messages");
    sessionStorage.removeItem("railmind_conversation_id");
    setSession(null);
    router.push("/login");
  }

  // Hide AppShell on login page
  if (pathname === "/login") {
    return <>{children}</>;
  }

  const email = session?.email || "Agent CAMRAIL";
  const role = session?.role || "Non connecté";
  const initial = email.charAt(0).toUpperCase();

  const navItems = [
    { name: t("app.assistant"), href: "/assistant" },
    { name: t("app.documents"), href: "/documents" },
    { name: t("app.dashboard"), href: "/" },
  ];

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 md:hidden" 
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-72 bg-slate-50 border-r border-slate-200 transform transition-transform duration-300 ease-in-out flex flex-col
        md:relative md:translate-x-0
        ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Sidebar Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between relative">
          <Link href="/" onClick={() => setMobileMenuOpen(false)} className="flex flex-col items-center justify-center gap-3 w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red rounded-lg p-1">
            <img 
              src="/camrail-logo-transparent.png" 
              alt="CAMRAIL Logo" 
              className="h-10 w-auto object-contain"
            />
            <div className="text-center">
              <p className="text-sm font-bold text-slate-900 leading-tight">RailMind Lite</p>
            </div>
          </Link>
          <button 
            className="md:hidden absolute top-4 right-4 text-slate-500 hover:text-slate-800 p-1 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Fermer le menu"
          >
            ✕
          </button>
        </div>

        {/* New Conversation Button */}
        <div className="p-4">
          <a
            href="/assistant"
            onClick={(e) => {
              e.preventDefault();
              setMobileMenuOpen(false);
              sessionStorage.removeItem("railmind_chat_messages");
              sessionStorage.removeItem("railmind_conversation_id");
              window.location.href = "/assistant";
            }}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-camrail-red px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-red-700 hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-camrail-red active:translate-y-px"
          >
            <span className="text-base font-bold">+</span> {t("app.new_chat")}
          </a>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          <p className="px-3 text-xs font-bold uppercase tracking-wider text-slate-600 mb-2 mt-4">{t("app.menu")}</p>
          {navItems.filter((item) => {
            if (item.name === t("app.dashboard") || item.name === t("app.documents")) {
              return session?.role === 'admin' || session?.role === 'document_admin';
            }
            return true;
          }).map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`
                  block px-3 py-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red
                  ${isActive 
                    ? 'bg-red-50/70 text-camrail-red font-semibold border-l-2 border-camrail-red rounded-r-lg' 
                    : 'text-slate-700 font-medium hover:bg-slate-100 hover:text-slate-900 rounded-lg border-l-2 border-transparent'
                  }
                `}
              >
                {item.name}
              </Link>
            );
          })}

          {/* Historique des discussions */}
          {session && (
            <>
              <p className="px-3 text-xs font-bold uppercase tracking-wider text-slate-600 mb-2 mt-6">{t("app.history")}</p>
              {conversations.length === 0 ? (
                <p className="px-3 text-xs text-slate-500 italic">
                  {language === 'fr' ? 'Aucune conversation récente' : 'No recent conversations'}
                </p>
              ) : (
                <div className="space-y-1">
                  {conversations.map((conv) => (
                    <Link
                      key={conv.id}
                      href={`/assistant?c=${conv.id}`}
                      onClick={() => setMobileMenuOpen(false)}
                      className="block rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 truncate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red"
                      title={conv.title}
                    >
                      {conv.title}
                    </Link>
                  ))}
                </div>
              )}
            </>
          )}
        </nav>

        {/* User Profile */}
        <div className="border-t border-slate-100 p-4">
          {session ? (
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-700">
                {initial}
              </div>
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900">{email}</p>
                <p className="truncate text-xs font-medium text-slate-600">{role}</p>
              </div>
              <button 
                onClick={handleLogout}
                className="text-slate-500 hover:text-camrail-red p-1 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red transition-colors"
                title="Se déconnecter"
                aria-label="Se déconnecter"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
              </button>
            </div>
          ) : (
            <Link 
              href="/login"
              onClick={() => setMobileMenuOpen(false)}
              className="block text-center text-sm font-medium text-camrail-red hover:underline"
            >
              {t("app.logout").replace('Se déconnecter', 'Se connecter').replace('Logout', 'Login')}
            </Link>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile Topbar */}
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 md:hidden">
          <button
            type="button"
            className="text-slate-500 hover:text-slate-700"
            onClick={() => setMobileMenuOpen(true)}
          >
            ☰
          </button>
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-900">CAMRAIL</span>
          </div>
          <div className="w-6" /> {/* Spacer for centering */}
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}