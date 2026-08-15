"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { clearSession, getSession } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

export default function AppShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

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
    { name: "Assistant IA", href: "/assistant" },
    { name: "Documents", href: "/documents" },
    { name: "Dashboard", href: "/" },
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
        fixed inset-y-0 left-0 z-50 w-72 bg-white border-r border-slate-200 transform transition-transform duration-300 ease-in-out flex flex-col
        md:relative md:translate-x-0
        ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Sidebar Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between relative">
          <Link href="/" onClick={() => setMobileMenuOpen(false)} className="flex flex-col items-center justify-center gap-3 w-full">
            <img 
              src="/camrail-logo.png" 
              alt="CAMRAIL Logo" 
              className="h-10 w-auto object-contain"
            />
            <div className="text-center">
              <p className="text-sm font-bold text-slate-900 leading-tight">RailMind Lite</p>
            </div>
          </Link>
          <button 
            className="md:hidden absolute top-4 right-4 text-slate-400 hover:text-slate-600"
            onClick={() => setMobileMenuOpen(false)}
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
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-camrail-red px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-camrail-red-dark"
          >
            <span>+</span> Nouvelle conversation
          </a>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          <p className="px-3 text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 mt-4">Menu principal</p>
          {navItems.filter((item) => {
            if (item.name === 'Dashboard' || item.name === 'Documents') {
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
                  block rounded-lg px-3 py-2.5 text-sm font-medium transition-colors
                  ${isActive 
                    ? 'bg-camrail-red-light text-camrail-red font-semibold' 
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
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
              <p className="px-3 text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 mt-6">Historique</p>
              {conversations.length === 0 ? (
                <p className="px-3 text-xs text-slate-500 italic">Aucune conversation</p>
              ) : (
                <div className="space-y-1">
                  {conversations.map((conv) => (
                    <Link
                      key={conv.id}
                      href={`/assistant?c=${conv.id}`}
                      onClick={() => setMobileMenuOpen(false)}
                      className="block rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900 truncate"
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
                <p className="truncate text-xs text-slate-500">{role}</p>
              </div>
              <button 
                onClick={handleLogout}
                className="text-slate-400 hover:text-camrail-red transition-colors"
                title="Se déconnecter"
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
              Se connecter
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