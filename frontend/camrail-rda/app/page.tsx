"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { useLanguage } from "@/lib/LanguageContext";
import { Modal } from "@/components/ui/modal";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  formatAuditAction,
  formatConfidence,
  getConfidenceDescription,
  formatDocumentStatus,
  getDocumentStatusDescription,
} from "@/lib/labels";

type DashboardSummary = {
  documents_total: number;
  documents_by_status: Record<string, number>;
  documents_active: number;
  questions_total: number;
  questions_today: number;
  confidence_breakdown: Record<string, number>;
  recent_audit_count: number;
};

type QueryDetail = {
  id?: string | number;
  created_at: string;
  user_email: string;
  query_text: string;
  confidence: "high" | "medium" | "insufficient";
};

type AuditDetail = {
  id?: string | number;
  created_at: string;
  user_email: string;
  action: string;
  entity_type?: string;
  details?: string;
};

export default function DashboardPage() {
  const { language, t } = useLanguage();

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showQueriesModal, setShowQueriesModal] = useState(false);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [queriesData, setQueriesData] = useState<QueryDetail[]>([]);
  const [auditData, setAuditData] = useState<AuditDetail[]>([]);

  async function fetchQueries() {
    setShowQueriesModal(true);
    setModalLoading(true);
    try {
      const data = await apiFetch("/dashboard/details/queries");
      setQueriesData(Array.isArray(data) ? (data as QueryDetail[]) : []);
    } catch (err) {
      console.error("Erreur lors de la récupération des requêtes:", err);
      setQueriesData([]);
    } finally {
      setModalLoading(false);
    }
  }

  async function fetchAudit() {
    setShowAuditModal(true);
    setModalLoading(true);
    try {
      const data = await apiFetch("/dashboard/details/audit");
      setAuditData(Array.isArray(data) ? (data as AuditDetail[]) : []);
    } catch (err) {
      console.error("Erreur lors de la récupération des logs d'audit:", err);
      setAuditData([]);
    } finally {
      setModalLoading(false);
    }
  }

  useEffect(() => {
    async function fetchSummary() {
      try {
        setLoading(true);
        const data = await apiFetch("/dashboard/summary");
        setSummary(data as DashboardSummary);
      } catch (err: any) {
        if (err.status === 403) {
          window.location.href = "/assistant";
        } else {
          setError(
            language === "fr"
              ? "Erreur lors du chargement des statistiques."
              : "Error loading statistics.",
          );
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
  }, [language]);

  // Calcul du taux de fiabilité
  const reliability = useMemo(() => {
    if (!summary?.confidence_breakdown) {
      return { total: 0, high: 0, medium: 0, insufficient: 0, reliablePct: 100, highPct: 0, mediumPct: 0, insufficientPct: 0 };
    }
    const high = summary.confidence_breakdown["high"] || 0;
    const medium = summary.confidence_breakdown["medium"] || 0;
    const insufficient = summary.confidence_breakdown["insufficient"] || 0;
    const total = high + medium + insufficient;

    if (total === 0) {
      return { total: 0, high: 0, medium: 0, insufficient: 0, reliablePct: 100, highPct: 0, mediumPct: 0, insufficientPct: 0 };
    }

    const reliablePct = Math.round(((high + medium) / total) * 100);
    const highPct = Math.round((high / total) * 100);
    const mediumPct = Math.round((medium / total) * 100);
    const insufficientPct = Math.max(0, 100 - highPct - mediumPct);

    return { total, high, medium, insufficient, reliablePct, highPct, mediumPct, insufficientPct };
  }, [summary]);

  return (
    <AuthGuard>
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 pb-16">
        {/* En-tête */}
        <div className="mb-8">
          <p className="text-xs font-bold uppercase tracking-widest text-camrail-red mb-1">
            CAMRAIL RailMind Lite
          </p>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            {language === "fr" ? "Tableau de Bord" : "Dashboard"}
          </h1>
          <p className="mt-1.5 text-sm text-slate-600 max-w-2xl leading-relaxed">
            {language === "fr"
              ? "Aperçu global de l'activité de l'assistant documentaire et du référentiel technique."
              : "Global overview of AI assistant activity and technical document repository."}
          </p>
        </div>

        {/* État de chargement */}
        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-16 flex flex-col items-center justify-center shadow-xs">
            <div className="h-8 w-8 rounded-full border-2 border-camrail-red border-t-transparent animate-spin mb-4"></div>
            <p className="text-sm font-medium text-slate-600">
              {language === "fr" ? "Chargement des indicateurs..." : "Loading indicators..."}
            </p>
          </div>
        )}

        {/* État d'erreur */}
        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 shadow-xs">
            <p className="text-sm font-bold text-red-700">
              {language === "fr" ? "Erreur de chargement" : "Loading error"}
            </p>
            <p className="mt-1 text-sm text-red-600">{error}</p>
          </div>
        )}

        {/* Données du Dashboard */}
        {!loading && !error && summary && (
          <div className="space-y-6">
            {/* Section 1 : Activité & Fiabilité de l'IA */}
            <div>
              <h2 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-camrail-red"></span>
                {language === "fr" ? "Activité de l'Assistant IA" : "AI Assistant Activity"}
              </h2>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {/* Métrique des requêtes avec jauge d'activité journalière */}
                <Card
                  onClick={fetchQueries}
                  className="p-5 hover:border-camrail-red/60 hover:shadow-md cursor-pointer transition-all flex flex-col justify-between"
                  title={language === "fr" ? "Cliquer pour voir les requêtes détaillées" : "Click to view query details"}
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        {language === "fr" ? "Requêtes aujourd'hui" : "Queries today"}
                      </p>
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-red-50 text-camrail-red">
                        {language === "fr" ? "Détails →" : "Details →"}
                      </span>
                    </div>
                    <p className="mt-2 text-4xl font-black text-slate-900 tracking-tight">
                      {summary.questions_today}
                    </p>
                    <p className="text-xs text-slate-500 mt-1 font-medium">
                      {language === "fr"
                        ? `Sur un cumul historique de ${summary.questions_total} requêtes`
                        : `Out of ${summary.questions_total} all-time queries`}
                    </p>
                  </div>

                  {/* Indicateur de volume */}
                  <div className="mt-6 pt-4 border-t border-slate-100">
                    <div className="flex items-center justify-between text-xs text-slate-600 mb-1.5 font-medium">
                      <span>{language === "fr" ? "Part journalière" : "Daily share"}</span>
                      <span className="font-bold text-slate-800">
                        {summary.questions_total > 0
                          ? `${Math.round((summary.questions_today / summary.questions_total) * 100)} %`
                          : "0 %"}
                      </span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-camrail-red rounded-full transition-all duration-500"
                        style={{
                          width: `${
                            summary.questions_total > 0
                              ? Math.min(100, Math.max(5, (summary.questions_today / summary.questions_total) * 100))
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                </Card>

                {/* KPI de Fiabilité Global & Barre de progression segmentée */}
                <Card className="p-5 lg:col-span-2 flex flex-col justify-between">
                  <div>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                          {language === "fr" ? "Fiabilité des réponses" : "Response Reliability"}
                        </p>
                        <p className="mt-1 text-xl sm:text-2xl font-bold text-slate-900">
                          {language === "fr"
                            ? `${reliability.reliablePct} % de réponses à confiance élevée ou moyenne`
                            : `${reliability.reliablePct}% high or medium confidence answers`}
                        </p>
                      </div>
                      <span className="text-xs font-medium text-slate-500">
                        {reliability.total} {language === "fr" ? "réponses évaluées" : "evaluated answers"}
                      </span>
                    </div>

                    {/* Barre de progression multi-segments */}
                    <div className="mt-4">
                      <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
                        <div
                          className="h-full bg-emerald-500 transition-all duration-500"
                          style={{ width: `${reliability.highPct}%` }}
                          title={`Élevée : ${reliability.highPct}% (${reliability.high})`}
                        />
                        <div
                          className="h-full bg-amber-400 transition-all duration-500"
                          style={{ width: `${reliability.mediumPct}%` }}
                          title={`Moyenne : ${reliability.mediumPct}% (${reliability.medium})`}
                        />
                        <div
                          className="h-full bg-red-400 transition-all duration-500"
                          style={{ width: `${reliability.insufficientPct}%` }}
                          title={`Insuffisante : ${reliability.insufficientPct}% (${reliability.insufficient})`}
                        />
                      </div>
                    </div>
                  </div>

                  {/* 3 Pastilles détaillées et cliquables */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6 pt-4 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={fetchQueries}
                      className="rounded-xl bg-emerald-50/80 border border-emerald-200/80 p-3 text-left hover:bg-emerald-100/70 transition-colors cursor-pointer group"
                      title={getConfidenceDescription("high", language)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-emerald-800 uppercase tracking-wide">
                          {formatConfidence("high", language)}
                        </span>
                        <span className="text-[11px] font-semibold text-emerald-700">
                          {reliability.highPct}%
                        </span>
                      </div>
                      <p className="text-xl font-bold text-emerald-950 mt-1">
                        {reliability.high}
                      </p>
                      <p className="text-[11px] text-emerald-700/90 mt-0.5 line-clamp-1">
                        {getConfidenceDescription("high", language)}
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={fetchQueries}
                      className="rounded-xl bg-amber-50/80 border border-amber-200/80 p-3 text-left hover:bg-amber-100/70 transition-colors cursor-pointer group"
                      title={getConfidenceDescription("medium", language)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-amber-800 uppercase tracking-wide">
                          {formatConfidence("medium", language)}
                        </span>
                        <span className="text-[11px] font-semibold text-amber-700">
                          {reliability.mediumPct}%
                        </span>
                      </div>
                      <p className="text-xl font-bold text-amber-950 mt-1">
                        {reliability.medium}
                      </p>
                      <p className="text-[11px] text-amber-700/90 mt-0.5 line-clamp-1">
                        {getConfidenceDescription("medium", language)}
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={fetchQueries}
                      className="rounded-xl bg-red-50/80 border border-red-200/80 p-3 text-left hover:bg-red-100/70 transition-colors cursor-pointer group"
                      title={getConfidenceDescription("insufficient", language)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-red-800 uppercase tracking-wide">
                          {formatConfidence("insufficient", language)}
                        </span>
                        <span className="text-[11px] font-semibold text-red-700">
                          {reliability.insufficientPct}%
                        </span>
                      </div>
                      <p className="text-xl font-bold text-red-950 mt-1">
                        {reliability.insufficient}
                      </p>
                      <p className="text-[11px] text-red-700/90 mt-0.5 line-clamp-1">
                        {getConfidenceDescription("insufficient", language)}
                      </p>
                    </button>
                  </div>
                </Card>
              </div>
            </div>

            {/* Section 2 : Référentiel Documentaire & Sécurité / Audit */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-8">
              {/* Référentiel Documentaire */}
              <div>
                <h2 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-slate-500"></span>
                  {language === "fr" ? "Référentiel Documentaire" : "Document Repository"}
                </h2>
                <Link href="/documents" className="grid grid-cols-2 gap-4 group">
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs group-hover:border-slate-400 group-hover:bg-slate-50 transition-colors">
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                      {formatDocumentStatus("active", language)}
                    </p>
                    <p className="text-3xl font-black text-slate-900">
                      {summary.documents_active}
                    </p>
                    <p className="text-xs text-slate-500 mt-2 font-medium">
                      {language === "fr" ? "Consultables par l'assistant" : "Queryable by assistant"}
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs group-hover:border-slate-400 group-hover:bg-slate-50 transition-colors">
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                      {language === "fr" ? "Total Documents" : "Total Documents"}
                    </p>
                    <p className="text-3xl font-black text-slate-700">
                      {summary.documents_total}
                    </p>
                    <p className="text-xs text-slate-500 mt-2 font-medium">
                      {language === "fr" ? "Tous statuts confondus" : "All statuses combined"}
                    </p>
                  </div>
                </Link>
              </div>

              {/* Sécurité & Audit */}
              <div>
                <h2 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-slate-800"></span>
                  {language === "fr" ? "Sécurité & Audit (24h)" : "Security & Audit (24h)"}
                </h2>
                <div
                  onClick={fetchAudit}
                  className="rounded-xl border-0 bg-gradient-to-br from-slate-900 to-slate-800 text-white p-5 shadow-sm min-h-[126px] flex flex-col justify-between relative overflow-hidden hover:from-slate-800 hover:to-slate-700 cursor-pointer transition-all"
                  title={language === "fr" ? "Cliquer pour consulter le journal d'audit" : "Click to view audit log"}
                >
                  <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                    <svg xmlns="http://www.w3.org/2000/svg" width="68" height="68" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                  </div>
                  <div>
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-bold uppercase tracking-wider text-slate-300 relative z-10">
                        {language === "fr" ? "Événements tracés (24h)" : "Tracked events (24h)"}
                      </p>
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-white/10 text-white relative z-10">
                        {language === "fr" ? "Journal →" : "Log →"}
                      </span>
                    </div>
                    <p className="text-3xl font-black text-white mt-1 relative z-10">
                      {summary.recent_audit_count}
                    </p>
                  </div>
                  <p className="text-xs text-slate-300 mt-2 relative z-10 font-medium">
                    {language === "fr"
                      ? "Traçabilité intégrale et immuable en base souveraine"
                      : "Full and immutable traceability in sovereign database"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Modal Requêtes Récentes (Sans scroll horizontal, table-fixed, header sticky) */}
        <Modal
          isOpen={showQueriesModal}
          onClose={() => setShowQueriesModal(false)}
          title={language === "fr" ? "Requêtes Récentes de l'Assistant" : "Recent Assistant Queries"}
          size="4xl"
        >
          {modalLoading ? (
            <div className="p-12 text-center">
              <div className="h-8 w-8 mx-auto rounded-full border-2 border-camrail-red border-t-transparent animate-spin mb-3"></div>
              <p className="text-sm font-medium text-slate-600">
                {language === "fr" ? "Chargement des requêtes..." : "Loading queries..."}
              </p>
            </div>
          ) : queriesData.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-sm">
              {language === "fr" ? "Aucune requête enregistrée." : "No queries recorded."}
            </div>
          ) : (
            <div className="max-h-[60vh] overflow-y-auto border border-slate-200 rounded-xl">
              <table className="table-fixed w-full divide-y divide-slate-200 text-left">
                <thead className="sticky top-0 bg-slate-100 z-10 shadow-2xs">
                  <tr>
                    <th className="w-[20%] px-4 py-3 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      {language === "fr" ? "Date" : "Date"}
                    </th>
                    <th className="w-[25%] px-4 py-3 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      {language === "fr" ? "Utilisateur" : "User"}
                    </th>
                    <th className="w-[38%] px-4 py-3 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      {language === "fr" ? "Question posée" : "Question asked"}
                    </th>
                    <th className="w-[17%] px-4 py-3 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      {language === "fr" ? "Confiance" : "Confidence"}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {queriesData.map((q, i) => {
                    const conf = q.confidence || "insufficient";
                    const badgeVariant =
                      conf === "high" ? "success" : conf === "medium" ? "warning" : "danger";

                    return (
                      <tr key={i} className="hover:bg-slate-50/80 transition-colors">
                        <td className="px-4 py-3 text-xs font-medium text-slate-600 truncate">
                          {new Date(q.created_at).toLocaleString("fr-FR", {
                            day: "2-digit",
                            month: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td
                          className="px-4 py-3 text-sm font-medium text-slate-900 truncate"
                          title={q.user_email}
                        >
                          {q.user_email}
                        </td>
                        <td
                          className="px-4 py-3 text-sm text-slate-800 truncate"
                          title={q.query_text}
                        >
                          {q.query_text}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={badgeVariant}
                            size="sm"
                            title={getConfidenceDescription(conf, language)}
                          >
                            {formatConfidence(conf, language)}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Modal>

        {/* Modal Événements d'Audit (Sans scroll horizontal, table-fixed, header sticky) */}
        <Modal
          isOpen={showAuditModal}
          onClose={() => setShowAuditModal(false)}
          title={language === "fr" ? "Journal des Événements d'Audit (24h)" : "Audit Events Log (24h)"}
          size="4xl"
        >
          {modalLoading ? (
            <div className="p-12 text-center">
              <div className="h-8 w-8 mx-auto rounded-full border-2 border-camrail-red border-t-transparent animate-spin mb-3"></div>
              <p className="text-sm font-medium text-slate-600">
                {language === "fr" ? "Chargement du journal d'audit..." : "Loading audit log..."}
              </p>
            </div>
          ) : auditData.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-sm">
              {language === "fr" ? "Aucun événement d'audit récent." : "No recent audit events."}
            </div>
          ) : (
            <div className="max-h-[60vh] overflow-y-auto border border-slate-200 rounded-xl">
              <table className="table-fixed w-full divide-y divide-slate-200 text-left">
                <thead className="sticky top-0 bg-slate-100 z-10 shadow-2xs">
                  <tr>
                    <th className="w-[20%] px-4 py-3 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      {language === "fr" ? "Date" : "Date"}
                    </th>
                    <th className="w-[28%] px-4 py-3 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      {language === "fr" ? "Utilisateur" : "User"}
                    </th>
                    <th className="w-[32%] px-4 py-3 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      {language === "fr" ? "Action tracée" : "Logged action"}
                    </th>
                    <th className="w-[20%] px-4 py-3 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      {language === "fr" ? "Entité" : "Entity"}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {auditData.map((a, i) => (
                    <tr key={i} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3 text-xs font-medium text-slate-600 truncate">
                        {new Date(a.created_at).toLocaleString("fr-FR", {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td
                        className="px-4 py-3 text-sm font-medium text-slate-900 truncate"
                        title={a.user_email}
                      >
                        {a.user_email}
                      </td>
                      <td
                        className="px-4 py-3 text-sm text-slate-800 font-medium truncate"
                        title={formatAuditAction(a.action, language)}
                      >
                        {formatAuditAction(a.action, language)}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600 font-medium truncate">
                        {a.entity_type || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Modal>
      </div>
    </AuthGuard>
  );
}