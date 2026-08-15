"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch } from "@/lib/api";
import { getSession } from "@/lib/auth";

type DashboardSummary = {
  documents_total: number;
  documents_by_status: Record<string, number>;
  documents_active: number;
  questions_total: number;
  questions_today: number;
  confidence_breakdown: Record<string, number>;
  recent_audit_count: number;
};

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  
  const [showQueriesModal, setShowQueriesModal] = useState(false);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [queriesData, setQueriesData] = useState<any[]>([]);
  const [auditData, setAuditData] = useState<any[]>([]);

  async function fetchQueries() {
    setShowQueriesModal(true);
    setModalLoading(true);
    try {
      const data = await apiFetch("/dashboard/details/queries");
      setQueriesData(data as any[]);
    } catch (err) {
      console.error(err);
    } finally {
      setModalLoading(false);
    }
  }

  async function fetchAudit() {
    setShowAuditModal(true);
    setModalLoading(true);
    try {
      const data = await apiFetch("/dashboard/details/audit");
      setAuditData(data as any[]);
    } catch (err) {
      console.error(err);
    } finally {
      setModalLoading(false);
    }
  }

  useEffect(() => {
    async function fetchSummary() {
      try {
        const data = await apiFetch("/dashboard/summary");
        setSummary(data as DashboardSummary);
      } catch (err: any) {
        if (err.status === 403) {
          window.location.href = "/assistant";
        } else {
          setError("Erreur lors du chargement des statistiques.");
        }
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    if (typeof window !== "undefined") {
      const session = getSession();
      if (session && session.role === "read_only") {
        window.location.href = "/assistant";
        return;
      }
    }
    fetchSummary();
  }, []);

  return (
    <AuthGuard>
      <div className="max-w-6xl mx-auto pb-12">
        <div className="mb-8">
          <p className="text-xs font-bold uppercase tracking-widest text-camrail-red mb-1">
            CAMRAIL RailMind Lite
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Tableau de Bord
          </h1>
          <p className="mt-2 text-sm text-slate-500 max-w-2xl">
            Aperçu global de l'activité de l'assistant IA et du système de gestion documentaire.
          </p>
        </div>

        {loading && (
          <div className="rounded-xl border border-slate-200 bg-white p-16 flex flex-col items-center justify-center shadow-sm">
            <div className="h-8 w-8 rounded-full border-2 border-camrail-red border-t-transparent animate-spin mb-4"></div>
            <p className="text-sm font-medium text-slate-500">Chargement des statistiques...</p>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 shadow-sm">
            <p className="text-sm font-bold text-red-700">Erreur de chargement</p>
            <p className="mt-1 text-sm text-red-600">{error}</p>
          </div>
        )}

        {!loading && !error && summary && (
          <div className="space-y-6">
            
            {/* Section IA */}
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-camrail-red"></span>
                Activité de l'Assistant IA
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div 
                  onClick={() => fetchQueries()}
                  className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-camrail-red hover:bg-red-50 cursor-pointer transition-colors"
                >
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-1">Requêtes (Aujourd'hui)</p>
                  <p className="text-4xl font-bold text-slate-900">{summary.questions_today}</p>
                  <p className="text-xs text-slate-400 mt-2">Sur un total historique de {summary.questions_total}</p>
                </div>
                
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:col-span-2">
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-4">Score de confiance global</p>
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <div onClick={() => fetchQueries()} className="rounded-lg bg-emerald-50 border border-emerald-100 p-4 hover:bg-emerald-100 cursor-pointer transition-colors">
                      <p className="text-xs font-semibold text-emerald-700 uppercase truncate">Élevé</p>
                      <p className="text-2xl font-bold text-emerald-800 mt-1">{summary.confidence_breakdown["high"] || 0}</p>
                    </div>
                    <div onClick={() => fetchQueries()} className="rounded-lg bg-amber-50 border border-amber-100 p-4 hover:bg-amber-100 cursor-pointer transition-colors">
                      <p className="text-xs font-semibold text-amber-700 uppercase truncate">Moyen</p>
                      <p className="text-2xl font-bold text-amber-800 mt-1">{summary.confidence_breakdown["medium"] || 0}</p>
                    </div>
                    <div onClick={() => fetchQueries()} className="rounded-lg bg-red-50 border border-red-100 p-4 hover:bg-red-100 cursor-pointer transition-colors">
                      <p className="text-xs font-semibold text-red-700 uppercase truncate">Insuffisant</p>
                      <p className="text-2xl font-bold text-red-800 mt-1">{summary.confidence_breakdown["insufficient"] || 0}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Section Documents & Système */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
              
              <div>
                <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-slate-400"></span>
                  Référentiel Documentaire
                </h2>
                <Link href="/documents" className="grid grid-cols-2 gap-4 group">
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm group-hover:border-slate-400 group-hover:bg-slate-50 transition-colors">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-1">Documents Actifs</p>
                    <p className="text-3xl font-bold text-slate-900">{summary.documents_active}</p>
                    <p className="text-xs text-slate-400 mt-2">Prêts pour la recherche</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm group-hover:border-slate-400 group-hover:bg-slate-50 transition-colors">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-1">Documents au total</p>
                    <p className="text-3xl font-bold text-slate-700">{summary.documents_total}</p>
                    <p className="text-xs text-slate-400 mt-2">Tous statuts confondus</p>
                  </div>
                </Link>
              </div>
              
              <div>
                <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-slate-800"></span>
                  Sécurité & Audit
                </h2>
                <div 
                  onClick={() => fetchAudit()}
                  className="rounded-xl border border-slate-200 bg-slate-900 text-white p-5 shadow-sm h-[124px] flex flex-col justify-center relative overflow-hidden hover:bg-slate-800 cursor-pointer transition-colors"
                >
                  <div className="absolute top-0 right-0 p-4 opacity-10">
                    <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                  </div>
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-1 relative z-10">Activité (24h)</p>
                  <p className="text-3xl font-bold text-white relative z-10">{summary.recent_audit_count}</p>
                  <p className="text-xs text-slate-400 mt-2 relative z-10">Événements d'audit sécurisés</p>
                </div>
              </div>

            </div>

          </div>
        )}

        {/* Queries Modal */}
        {showQueriesModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
                <h3 className="text-lg font-bold text-slate-900">Requêtes Récentes</h3>
                <button onClick={() => setShowQueriesModal(false)} className="text-slate-400 hover:text-slate-600 transition-colors">✕</button>
              </div>
              <div className="p-6 overflow-y-auto">
                {modalLoading ? (
                  <p className="text-sm text-slate-500">Chargement...</p>
                ) : (
                  <table className="min-w-full divide-y divide-slate-200 text-left">
                    <thead>
                      <tr>
                        <th className="px-3 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Date</th>
                        <th className="px-3 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Utilisateur</th>
                        <th className="px-3 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Requête</th>
                        <th className="px-3 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Confiance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {queriesData.map((q, i) => (
                        <tr key={i} className="hover:bg-slate-50 transition-colors">
                          <td className="px-3 py-4 whitespace-nowrap text-xs text-slate-500">{new Date(q.created_at).toLocaleString('fr-FR')}</td>
                          <td className="px-3 py-4 whitespace-nowrap text-sm font-medium text-slate-900">{q.user_email}</td>
                          <td className="px-3 py-4 text-sm text-slate-600 max-w-md truncate" title={q.query_text}>{q.query_text}</td>
                          <td className="px-3 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${q.confidence === 'high' ? 'bg-emerald-100 text-emerald-800' : q.confidence === 'medium' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'}`}>
                              {q.confidence || "insufficient"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Audit Modal */}
        {showAuditModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
                <h3 className="text-lg font-bold text-slate-900">Événements d'Audit (24h)</h3>
                <button onClick={() => setShowAuditModal(false)} className="text-slate-400 hover:text-slate-600 transition-colors">✕</button>
              </div>
              <div className="p-6 overflow-y-auto">
                {modalLoading ? (
                  <p className="text-sm text-slate-500">Chargement...</p>
                ) : (
                  <table className="min-w-full divide-y divide-slate-200 text-left">
                    <thead>
                      <tr>
                        <th className="px-3 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Date</th>
                        <th className="px-3 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Utilisateur</th>
                        <th className="px-3 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Action</th>
                        <th className="px-3 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Entité</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {auditData.map((a, i) => (
                        <tr key={i} className="hover:bg-slate-50 transition-colors">
                          <td className="px-3 py-4 whitespace-nowrap text-xs text-slate-500">{new Date(a.created_at).toLocaleString('fr-FR')}</td>
                          <td className="px-3 py-4 whitespace-nowrap text-sm font-medium text-slate-900">{a.user_email}</td>
                          <td className="px-3 py-4 text-sm text-slate-600 font-semibold">{a.action}</td>
                          <td className="px-3 py-4 whitespace-nowrap text-sm text-slate-500">{a.entity_type || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}

      </div>
    </AuthGuard>
  );
}