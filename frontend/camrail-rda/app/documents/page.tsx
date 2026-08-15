"use client";

import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { DocumentItem } from "@/lib/backend-types";

// Keep DocumentStatus type inferred or import it if exported from backend-types
type DocumentStatus = "processing" | "indexed" | "active" | "failed" | "archived";

const statusConfig: Record<
  DocumentStatus,
  {
    label: string;
    className: string;
    dot: string;
  }
> = {
  processing: {
    label: "Traitement",
    className: "bg-amber-50 text-amber-700 border-amber-200",
    dot: "bg-amber-500",
  },
  indexed: {
    label: "Indexé",
    className: "bg-red-50 text-red-700 border-red-200",
    dot: "bg-red-500",
  },
  active: {
    label: "Actif",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  failed: {
    label: "Échec",
    className: "bg-slate-100 text-slate-800 border-slate-200",
    dot: "bg-slate-600",
  },
  archived: {
    label: "Archivé",
    className: "bg-gray-100 text-gray-700 border-gray-300",
    dot: "bg-gray-500",
  },
};

function formatDate(date: string) {
  try {
    return new Intl.DateTimeFormat("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(new Date(date));
  } catch {
    return date;
  }
}

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [role, setRole] = useState<string | null>(null);
  const [activateOnUpload, setActivateOnUpload] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isAdmin = role === "admin" || role === "document_admin";

  async function loadDocuments() {
    try {
      setLoading(true);
      setError("");
      const data = await apiFetch("/documents");
      setDocuments(data as DocumentItem[]);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Impossible de charger les documents."
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

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", file.name);
      formData.append("category", "Général");
      formData.append("department", "Opérations");
      formData.append("initial_status", activateOnUpload ? "active" : "indexed");

      await apiFetch("/documents", {
        method: "POST",
        body: formData,
      });

      await loadDocuments();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erreur lors de l'upload.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleStatusChange(id: string | number, currentStatus: string) {
    if (!isAdmin) return;
    try {
      const endpoint = currentStatus === "active" ? `/documents/${id}/archive` : `/documents/${id}/activate`;
      await apiFetch(endpoint, { method: "POST" });
      await loadDocuments();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erreur lors du changement de statut.");
    }
  }

  const filteredDocuments = documents.filter((document) =>
    document.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <AuthGuard>
      <div className="max-w-6xl mx-auto pb-12">
        {/* Header */}
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-camrail-red mb-1">
              CAMRAIL RailMind Lite
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">
              Gestion Documentaire
            </h1>
            <p className="mt-2 text-sm text-slate-500 max-w-2xl">
              Gérez le référentiel des documents techniques et opérationnels accessibles par l'assistant IA.
            </p>
          </div>

          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            className="hidden" 
            accept=".pdf,.docx" 
          />
          <div className="flex items-center gap-4">
            {isAdmin && (
              <label className="flex items-center gap-2 text-sm font-medium text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={activateOnUpload}
                  onChange={(e) => setActivateOnUpload(e.target.checked)}
                  className="rounded border-slate-300 text-camrail-red focus:ring-camrail-red"
                />
                Activer immédiatement
              </label>
            )}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-camrail-red px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-camrail-red-dark disabled:opacity-50"
            >
              <span className="text-lg leading-none">+</span>
              {uploading ? "Envoi..." : "Nouveau document"}
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Total</p>
            <p className="text-3xl font-bold text-slate-900">{documents.length}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Actifs</p>
            <p className="text-3xl font-bold text-emerald-600">
              {documents.filter((doc) => doc.status === "active").length}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Indexés</p>
            <p className="text-3xl font-bold text-slate-700">
              {documents.filter((doc) => doc.status === "indexed").length}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm border-b-4 border-b-amber-500">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">En traitement</p>
            <p className="text-3xl font-bold text-amber-600">
              {documents.filter((doc) => doc.status === "processing").length}
            </p>
          </div>
        </div>

        {/* Search */}
        <div className="mb-6 relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <svg className="h-5 w-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Rechercher par titre de document..."
            className="block w-full pl-10 pr-3 py-3 border border-slate-200 rounded-xl leading-5 bg-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-camrail-red focus:border-camrail-red sm:text-sm shadow-sm transition-all"
          />
        </div>

        {/* Loading */}
        {loading && (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm flex flex-col items-center justify-center">
             <div className="h-8 w-8 rounded-full border-2 border-camrail-red border-t-transparent animate-spin mb-4"></div>
            <p className="text-sm font-medium text-slate-500">Chargement de la base documentaire...</p>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center shadow-sm">
            <p className="text-sm font-bold text-red-700">Erreur de chargement</p>
            <p className="mt-1 text-sm text-red-600">{error}</p>
          </div>
        )}

        {/* Documents */}
        {!loading && !error && (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="hidden md:block overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                      Document
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                      Catégorie
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                      Département
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                      Mise à jour
                    </th>
                    <th scope="col" className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
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
                    const status = statusConfig[document.status as DocumentStatus] || statusConfig.failed;
                    return (
                      <tr key={document.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div className="flex-shrink-0 h-10 w-10 flex items-center justify-center rounded-lg bg-slate-100 text-slate-400">
                              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                            </div>
                            <div className="ml-4">
                              <div className="text-sm font-semibold text-slate-900">
                                <Link href={`/documents/${document.id}`} className="hover:text-camrail-red transition-colors">
                                  {document.title}
                                </Link>
                              </div>
                              <div className="text-xs text-slate-500 mt-0.5">
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
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 font-medium">
                          {document.department || "Tous"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                          {formatDate(document.created_at || "")}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${status.className}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`}></span>
                            {status.label}
                          </span>
                        </td>
                        {isAdmin && (
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            {(document.status === "indexed" || document.status === "archived") && (
                              <button onClick={() => handleStatusChange(document.id, document.status)} className="text-emerald-600 hover:text-emerald-900 bg-emerald-50 px-3 py-1 rounded-md transition-colors ml-2">
                                Activer
                              </button>
                            )}
                            {document.status === "active" && (
                              <button onClick={() => handleStatusChange(document.id, document.status)} className="text-amber-600 hover:text-amber-900 bg-amber-50 px-3 py-1 rounded-md transition-colors ml-2">
                                Archiver
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

            {/* Mobile cards */}
            <div className="divide-y divide-slate-100 md:hidden">
              {filteredDocuments.map((document) => {
                const status = statusConfig[document.status as DocumentStatus] || statusConfig.failed;
                return (
                  <div key={document.id} className="p-4 bg-white hover:bg-slate-50 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <Link href={`/documents/${document.id}`} className="block">
                          <p className="text-sm font-bold text-slate-900 truncate hover:text-camrail-red">
                            {document.title}
                          </p>
                        </Link>
                        <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                          <span className="font-medium text-slate-700">{document.category}</span>
                          <span>&bull;</span>
                          <span>{document.department}</span>
                          <span>&bull;</span>
                          <span>v{document.version}</span>
                        </div>
                      </div>
                      <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide border ${status.className}`}>
                        {status.label}
                      </span>
                    </div>
                    {isAdmin && (document.status === "indexed" || document.status === "archived") && (
                      <button onClick={() => handleStatusChange(document.id, document.status)} className="mt-3 w-full text-center text-emerald-600 font-medium hover:text-emerald-800 bg-emerald-50 py-2 rounded-lg text-sm transition-colors">
                        Activer le document
                      </button>
                    )}
                    {isAdmin && document.status === "active" && (
                      <button onClick={() => handleStatusChange(document.id, document.status)} className="mt-3 w-full text-center text-amber-600 font-medium hover:text-amber-800 bg-amber-50 py-2 rounded-lg text-sm transition-colors">
                        Archiver le document
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {filteredDocuments.length === 0 && (
              <div className="p-16 text-center">
                <svg className="mx-auto h-12 w-12 text-slate-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-base font-semibold text-slate-900">Aucun document trouvé</p>
                <p className="mt-1 text-sm text-slate-500">Essayez de modifier vos termes de recherche.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </AuthGuard>
  );
}
