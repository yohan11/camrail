"use client";

import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { useLanguage } from "@/lib/LanguageContext";
import type { DocumentItem } from "@/lib/backend-types";
import { Modal } from "@/components/ui/modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

type DocumentStatus = "processing" | "indexed" | "active" | "failed" | "archived";

const statusConfig: Record<
  string,
  {
    label: string;
    className: string;
    dot: string;
    tooltip: string;
  }
> = {
  active: {
    label: "Prêt",
    className: "bg-emerald-50 text-emerald-800 border-emerald-200",
    dot: "bg-emerald-500",
    tooltip: "Document validé et disponible pour l'interrogation par l'assistant IA",
  },
  indexed: {
    label: "Prêt",
    className: "bg-emerald-50 text-emerald-800 border-emerald-200",
    dot: "bg-emerald-500",
    tooltip: "Indexation vectorielle terminée avec succès, document prêt",
  },
  processing: {
    label: "En cours",
    className: "bg-amber-50 text-amber-800 border-amber-200",
    dot: "bg-amber-500",
    tooltip: "Extraction de texte et découpage en cours dans le moteur local",
  },
  failed: {
    label: "En erreur",
    className: "bg-red-50 text-red-800 border-red-200",
    dot: "bg-red-500",
    tooltip: "Échec d'extraction ou de vectorisation",
  },
  archived: {
    label: "Archivé",
    className: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-500",
    tooltip: "Document archivé et exclu du périmètre de recherche active",
  },
};

function formatRelativeDate(dateStr: string, lang: "fr" | "en" = "fr"): { relative: string; full: string } {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    const full = new Intl.DateTimeFormat(lang === "fr" ? "fr-FR" : "en-US", {
      day: "2-digit",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);

    if (diffMin < 2) {
      return { relative: lang === "fr" ? "à l'instant" : "just now", full };
    }
    if (diffMin < 60) {
      return { relative: lang === "fr" ? `il y a ${diffMin} min` : `${diffMin}m ago`, full };
    }
    if (diffHour < 24) {
      return { relative: lang === "fr" ? `il y a ${diffHour} h` : `${diffHour}h ago`, full };
    }
    if (diffDay === 1) {
      return { relative: lang === "fr" ? "hier" : "yesterday", full };
    }
    if (diffDay < 30) {
      return { relative: lang === "fr" ? `il y a ${diffDay} jours` : `${diffDay}d ago`, full };
    }
    return {
      relative: new Intl.DateTimeFormat(lang === "fr" ? "fr-FR" : "en-US", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).format(d),
      full,
    };
  } catch {
    return { relative: dateStr, full: dateStr };
  }
}

export default function DocumentsPage() {
  const { language, t } = useLanguage();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [role, setRole] = useState<string | null>(null);

  // Search & Filters state
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedDepartment, setSelectedDepartment] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadCategory, setUploadCategory] = useState("Général");
  const [uploadDepartment, setUploadDepartment] = useState("Opérations");
  const [activateOnUpload, setActivateOnUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isAdmin = role === "admin" || role === "document_admin";

  async function loadDocuments() {
    try {
      setLoading(true);
      setError("");
      const data = await apiFetch("/documents");
      setDocuments(data as DocumentItem[]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Impossible de charger les documents."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const session = getSession();
    if (session?.role === "read_only") {
      window.location.href = "/assistant";
      return;
    }
    loadDocuments();
    setRole(session?.role || null);
  }, []);

  // Check for stuck documents in processing for > 10 minutes
  const stuckDocuments = documents.filter((doc) => {
    if (doc.status !== "processing" || !doc.created_at) return false;
    try {
      const created = new Date(doc.created_at).getTime();
      return Date.now() - created > 10 * 60 * 1000;
    } catch {
      return false;
    }
  });

  async function handleRetryIndex(docId: string | number) {
    try {
      await apiFetch(`/documents/${docId}/retry`, { method: "POST" }).catch(() =>
        apiFetch(`/documents/${docId}/activate`, { method: "POST" })
      );
      await loadDocuments();
    } catch (err: any) {
      alert(err?.message || "Erreur lors de la relance.");
    }
  }

  async function handleStatusChange(id: string | number, currentStatus: string) {
    if (!isAdmin) return;
    try {
      const endpoint = currentStatus === "active" ? `/documents/${id}/archive` : `/documents/${id}/activate`;
      await apiFetch(endpoint, { method: "POST" });
      await loadDocuments();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erreur lors du changement de statut.");
    }
  }

  function handleFileSelected(file: File) {
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext !== "pdf" && ext !== "docx") {
      alert("Format non supporté. Veuillez sélectionner un fichier PDF ou DOCX.");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      alert("Le fichier dépasse la taille maximale autorisée de 50 Mo.");
      return;
    }
    setUploadFile(file);
    if (!uploadTitle.trim()) {
      setUploadTitle(file.name.replace(/\.[^/.]+$/, ""));
    }
  }

  async function handleSubmitUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) return;

    try {
      setUploading(true);
      setUploadProgress(15);
      const timer = setInterval(() => {
        setUploadProgress((prev) => (prev < 85 ? prev + 15 : prev));
      }, 300);

      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("title", uploadTitle.trim() || uploadFile.name);
      formData.append("category", uploadCategory);
      formData.append("department", uploadDepartment);
      formData.append("initial_status", activateOnUpload ? "active" : "indexed");

      await apiFetch("/documents", {
        method: "POST",
        body: formData,
      });

      clearInterval(timer);
      setUploadProgress(100);
      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
        setShowUploadModal(false);
        setUploadFile(null);
        setUploadTitle("");
        loadDocuments();
      }, 500);
    } catch (err: any) {
      setUploading(false);
      setUploadProgress(0);
      alert(err instanceof Error ? err.message : "Erreur lors de l'upload.");
    }
  }

  // Categories & Departments options
  const categories = Array.from(new Set(documents.map((d) => d.category).filter(Boolean)));
  const departments = Array.from(new Set(documents.map((d) => d.department).filter(Boolean)));

  // Filtered documents
  const filteredDocuments = documents.filter((doc) => {
    // Search
    const matchesSearch = doc.title.toLowerCase().includes(search.toLowerCase());
    // Category
    const matchesCategory = selectedCategory === "all" || doc.category === selectedCategory;
    // Department
    const matchesDepartment = selectedDepartment === "all" || doc.department === selectedDepartment;
    // Status
    let matchesStatus = true;
    if (selectedStatus === "ready") {
      matchesStatus = doc.status === "active" || doc.status === "indexed";
    } else if (selectedStatus !== "all") {
      matchesStatus = doc.status === selectedStatus;
    }
    return matchesSearch && matchesCategory && matchesDepartment && matchesStatus;
  });

  const readyCount = documents.filter((d) => d.status === "active" || d.status === "indexed").length;
  const processingCount = documents.filter((d) => d.status === "processing").length;
  const failedCount = documents.filter((d) => d.status === "failed").length;
  const archivedCount = documents.filter((d) => d.status === "archived").length;

  return (
    <AuthGuard>
      <div className="max-w-6xl mx-auto pb-16 px-4 sm:px-6">
        {/* Header */}
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-camrail-red mb-1">
              CAMRAIL RailMind Lite
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">
              {t("docs.title")}
            </h1>
            <p className="mt-2 text-sm text-slate-600 max-w-2xl leading-relaxed">
              {t("docs.subtitle")}
            </p>
          </div>

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => setShowUploadModal(true)}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-camrail-red px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-red-700 hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-camrail-red active:translate-y-px cursor-pointer"
            >
              <span className="text-lg leading-none font-bold">+</span>
              {t("docs.new_button")}
            </button>
          </div>
        </div>

        {/* Warning banner for stuck documents */}
        {stuckDocuments.length > 0 && (
          <div className="mb-6 rounded-xl border border-amber-300 bg-amber-50/90 p-4 shadow-sm">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <span className="text-amber-600 text-lg">⚠️</span>
                <div>
                  <p className="text-sm font-bold text-amber-950">
                    {stuckDocuments.length === 1
                      ? t("docs.stuck_warning")
                      : `${stuckDocuments.length} documents sont en cours de traitement depuis plus de 10 minutes.`}
                  </p>
                  <p className="text-xs text-amber-800 mt-0.5">
                    {stuckDocuments.map((d) => d.title).join(", ")}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => stuckDocuments.forEach((d) => handleRetryIndex(d.id))}
                className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 cursor-pointer"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-10.05l5.67-5.67"/></svg>
                <span>{t("docs.retry_index")}</span>
              </button>
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {/* Prêts */}
          <div 
            title={statusConfig.active.tooltip}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-emerald-200 transition-colors cursor-help"
          >
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("docs.status_ready")}
              </p>
              <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
            </div>
            <p className="text-3xl font-bold text-emerald-600">{readyCount}</p>
            <p className="text-xs text-slate-500 mt-1 truncate">Actifs & indexés</p>
          </div>

          {/* En cours */}
          <div 
            title={statusConfig.processing.tooltip}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-amber-200 transition-colors cursor-help"
          >
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("docs.status_processing")}
              </p>
              <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse"></span>
            </div>
            <p className="text-3xl font-bold text-amber-600">{processingCount}</p>
            <p className="text-xs text-slate-500 mt-1 truncate">Indexation locale</p>
          </div>

          {/* En erreur */}
          <div 
            title={statusConfig.failed.tooltip}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-red-200 transition-colors cursor-help"
          >
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("docs.status_failed")}
              </p>
              <span className="h-2 w-2 rounded-full bg-red-500"></span>
            </div>
            <p className="text-3xl font-bold text-red-600">{failedCount}</p>
            <p className="text-xs text-slate-500 mt-1 truncate">Échec d'analyse</p>
          </div>

          {/* Archivés */}
          <div 
            title={statusConfig.archived.tooltip}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-slate-300 transition-colors cursor-help"
          >
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("docs.status_archived")}
              </p>
              <span className="h-2 w-2 rounded-full bg-slate-500"></span>
            </div>
            <p className="text-3xl font-bold text-slate-700">{archivedCount}</p>
            <p className="text-xs text-slate-500 mt-1 truncate">Retirés de recherche</p>
          </div>
        </div>

        {/* Search & Filters Bar */}
        <div className="mb-6 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
            {/* Search Input */}
            <div className="sm:col-span-5 relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("docs.search_placeholder")}
                className="block w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-xl leading-5 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-camrail-red/20 focus:border-camrail-red text-sm shadow-sm transition-all"
              />
            </div>

            {/* Filter: Category */}
            <div className="sm:col-span-2">
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="block w-full py-2.5 px-3 border border-slate-200 rounded-xl bg-white text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-camrail-red/20 focus:border-camrail-red shadow-sm"
              >
                <option value="all">{t("docs.filter_category")}</option>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Filter: Department */}
            <div className="sm:col-span-2">
              <select
                value={selectedDepartment}
                onChange={(e) => setSelectedDepartment(e.target.value)}
                className="block w-full py-2.5 px-3 border border-slate-200 rounded-xl bg-white text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-camrail-red/20 focus:border-camrail-red shadow-sm"
              >
                <option value="all">{t("docs.filter_department")}</option>
                {departments.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            {/* Filter: Status */}
            <div className="sm:col-span-3">
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="block w-full py-2.5 px-3 border border-slate-200 rounded-xl bg-white text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-camrail-red/20 focus:border-camrail-red shadow-sm"
              >
                <option value="all">{t("docs.filter_all")}</option>
                <option value="ready">{t("docs.status_ready")}</option>
                <option value="processing">{t("docs.status_processing")}</option>
                <option value="failed">{t("docs.status_failed")}</option>
                <option value="archived">{t("docs.status_archived")}</option>
              </select>
            </div>
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm flex flex-col items-center justify-center">
            <div className="h-8 w-8 rounded-full border-2 border-camrail-red border-t-transparent animate-spin mb-4"></div>
            <p className="text-sm font-medium text-slate-600">Chargement de la base documentaire...</p>
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center shadow-sm">
            <p className="text-sm font-bold text-red-700">Erreur de chargement</p>
            <p className="mt-1 text-sm text-red-600">{error}</p>
          </div>
        )}

        {/* Documents Table */}
        {!loading && !error && (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="hidden md:block overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                      Document
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                      Catégorie
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                      Département
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                      Mise à jour
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                      Statut
                    </th>
                    {isAdmin && (
                      <th scope="col" className="relative px-6 py-4">
                        <span className="sr-only">Actions</span>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-100">
                  {filteredDocuments.map((document) => {
                    const status = statusConfig[document.status] || statusConfig.failed;
                    const dateInfo = formatRelativeDate(document.created_at || "", language);

                    return (
                      <tr key={document.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div className="shrink-0 h-10 w-10 flex items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                            </div>
                            <div className="ml-4">
                              <div className="text-sm font-semibold text-slate-900">
                                <Link href={`/documents/${document.id}`} className="hover:text-camrail-red transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red rounded">
                                  {document.title}
                                </Link>
                              </div>
                              <div className="text-xs font-medium text-slate-600 mt-0.5">
                                Version {document.version}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                            {document.category || "Général"}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 font-medium">
                          {document.department || "Tous"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-600">
                          <span title={dateInfo.full} className="cursor-help">
                            {dateInfo.relative}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span 
                            title={status.tooltip}
                            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border cursor-help ${status.className}`}
                          >
                            <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`}></span>
                            {status.label}
                          </span>
                        </td>
                        {isAdmin && (
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            {(document.status === "indexed" || document.status === "archived") && (
                              <button onClick={() => handleStatusChange(document.id, document.status)} title="Activer" className="text-slate-500 hover:text-emerald-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors ml-2 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-10.05l5.67-5.67"/></svg>
                              </button>
                            )}
                            {document.status === "active" && (
                              <button onClick={() => handleStatusChange(document.id, document.status)} title="Archiver" className="text-slate-500 hover:text-red-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors ml-2 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>
                              </button>
                            )}
                            {document.status === "processing" && (
                              <button onClick={() => handleRetryIndex(document.id)} title="Relancer l'indexation" className="text-slate-500 hover:text-amber-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors ml-2 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-10.05l5.67-5.67"/></svg>
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards */}
            <div className="divide-y divide-slate-100 md:hidden">
              {filteredDocuments.map((document) => {
                const status = statusConfig[document.status] || statusConfig.failed;
                const dateInfo = formatRelativeDate(document.created_at || "", language);

                return (
                  <div key={document.id} className="p-4 bg-white hover:bg-slate-50 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <Link href={`/documents/${document.id}`} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red rounded">
                          <p className="text-sm font-bold text-slate-900 truncate hover:text-camrail-red">
                            {document.title}
                          </p>
                        </Link>
                        <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-600">
                          <span className="font-semibold text-slate-700">{document.category || "Général"}</span>
                          <span>&bull;</span>
                          <span>{document.department || "Tous"}</span>
                          <span>&bull;</span>
                          <span title={dateInfo.full}>{dateInfo.relative}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span 
                          title={status.tooltip}
                          className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold border ${status.className}`}
                        >
                          {status.label}
                        </span>
                        {isAdmin && (document.status === "indexed" || document.status === "archived") && (
                          <button onClick={() => handleStatusChange(document.id, document.status)} title="Activer" className="text-slate-500 hover:text-emerald-600 p-1 rounded transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-10.05l5.67-5.67"/></svg>
                          </button>
                        )}
                        {isAdmin && document.status === "active" && (
                          <button onClick={() => handleStatusChange(document.id, document.status)} title="Archiver" className="text-slate-500 hover:text-red-600 p-1 rounded transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Empty state when no documents match filters */}
            {filteredDocuments.length === 0 && (
              <div className="py-12 px-4">
                <EmptyState
                  title={t("docs.empty_title")}
                  description={t("docs.empty_desc")}
                  action={
                    (search || selectedCategory !== "all" || selectedDepartment !== "all" || selectedStatus !== "all") ? (
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setSearch("");
                          setSelectedCategory("all");
                          setSelectedDepartment("all");
                          setSelectedStatus("all");
                        }}
                      >
                        {t("docs.reset_filters")}
                      </Button>
                    ) : undefined
                  }
                />
              </div>
            )}
          </div>
        )}

        {/* Upload Modal with Drag and Drop */}
        <Modal
          isOpen={showUploadModal}
          onClose={() => {
            if (!uploading) {
              setShowUploadModal(false);
              setUploadFile(null);
            }
          }}
          title={t("docs.upload_modal_title")}
          size="lg"
        >
          <form onSubmit={handleSubmitUpload} className="space-y-4">
            {/* Drag & Drop Zone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setIsDragging(false);
              }}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                const file = e.dataTransfer.files?.[0];
                if (file) handleFileSelected(file);
              }}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                isDragging
                  ? "border-camrail-red bg-red-50/50"
                  : uploadFile
                  ? "border-emerald-400 bg-emerald-50/30"
                  : "border-slate-300 hover:border-slate-400 bg-slate-50/50"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.docx"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileSelected(file);
                }}
              />
              <div className="flex flex-col items-center justify-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className={uploadFile ? "text-emerald-600" : "text-slate-400"}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                {uploadFile ? (
                  <div>
                    <p className="text-sm font-bold text-emerald-900">{uploadFile.name}</p>
                    <p className="text-xs text-emerald-700 mt-0.5">
                      {(uploadFile.size / (1024 * 1024)).toFixed(2)} Mo • Cliquez pour changer
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      {t("docs.upload_drag_title")}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      {t("docs.upload_drag_sub")}
                    </p>
                  </div>
                )}
                <span className="text-[11px] font-medium text-slate-500 mt-2">
                  {t("docs.upload_format_hint")}
                </span>
              </div>
            </div>

            {/* Document Details */}
            <div className="space-y-3 pt-2">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Titre du document
                </label>
                <input
                  type="text"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="Ex : Consignes de sécurité signalisation..."
                  className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-camrail-red/20 focus:border-camrail-red"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                    Catégorie
                  </label>
                  <select
                    value={uploadCategory}
                    onChange={(e) => setUploadCategory(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-camrail-red/20 focus:border-camrail-red"
                  >
                    <option value="Général">Général</option>
                    <option value="Sécurité">Sécurité</option>
                    <option value="Maintenance">Maintenance</option>
                    <option value="Signalisation">Signalisation</option>
                    <option value="Réglementation">Réglementation</option>
                    <option value="Infrastructure">Infrastructure</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                    Département
                  </label>
                  <select
                    value={uploadDepartment}
                    onChange={(e) => setUploadDepartment(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-camrail-red/20 focus:border-camrail-red"
                  >
                    <option value="Opérations">Opérations</option>
                    <option value="Matériel">Matériel</option>
                    <option value="Voies">Voies</option>
                    <option value="Sécurité">Sécurité</option>
                    <option value="Tous">Tous</option>
                  </select>
                </div>
              </div>

              {isAdmin && (
                <label className="flex items-center gap-2 pt-1 text-xs font-medium text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={activateOnUpload}
                    onChange={(e) => setActivateOnUpload(e.target.checked)}
                    className="rounded border-slate-300 text-camrail-red focus:ring-camrail-red"
                  />
                  <span>Rendre immédiatement actif pour l'assistant</span>
                </label>
              )}
            </div>

            {/* Progress Bar during upload */}
            {uploading && (
              <div className="pt-2">
                <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                  <span>{t("docs.upload_progress")}</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-camrail-red h-2 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                disabled={uploading}
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadFile(null);
                }}
                className="px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={!uploadFile || uploading}
                className="px-5 py-2 text-sm font-bold text-white bg-camrail-red hover:bg-red-700 rounded-lg transition-colors shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {uploading ? (
                  <>
                    <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin"></span>
                    <span>Importation...</span>
                  </>
                ) : (
                  <span>Importer</span>
                )}
              </button>
            </div>
          </form>
        </Modal>
      </div>
    </AuthGuard>
  );
}
