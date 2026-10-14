"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch } from "@/lib/api";
import { getAccessToken, getSession } from "@/lib/auth";
import { findNormalized } from "@/lib/find-normalized";

type DocumentPage = {
  id: string | number;
  page_number: number;
  extracted_text: string;
  extraction_method?: string;
};

type DocumentDetail = {
  id: string | number;
  title: string;
  category: string;
  department: string;
  version: string;
  status: "processing" | "indexed" | "active" | "failed";
  file_type?: "pdf" | "docx" | "other";
  checksum: string;
  uploaded_by: string | number;
  created_at: string;
  pages: DocumentPage[];
};

type EvidenceItem = {
  page_number: number;
  text: string;
};

export default function DocumentViewerPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const documentId = String(params.id);

  const initialPageParam = parseInt(searchParams.get("page") || "1", 10) || 1;
  const [currentPage, setCurrentPage] = useState<number>(initialPageParam);
  const [nonce, setNonce] = useState<number>(0);

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fileError, setFileError] = useState("");
  const [fileUrl, setFileUrl] = useState<string | null>(null);

  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([]);

  // Load evidence from localStorage (TTL: 1 hour)
  useEffect(() => {
    if (typeof window === "undefined" || !documentId) return;
    try {
      const raw = window.localStorage.getItem(`evidence:${documentId}`);
      if (!raw) return;

      const parsed = JSON.parse(raw);
      const ONE_HOUR = 60 * 60 * 1000;
      if (parsed?.savedAt && Date.now() - parsed.savedAt < ONE_HOUR && Array.isArray(parsed.items)) {
        setEvidenceItems(parsed.items);
      } else {
        window.localStorage.removeItem(`evidence:${documentId}`);
      }
    } catch {
      // ignore
    }
  }, [documentId]);

  // Load document detail and sort pages ONCE
  useEffect(() => {
    async function loadDocument() {
      try {
        setLoading(true);
        setError("");

        const data = await apiFetch(`/documents/${documentId}`);
        const rawDoc = data as DocumentDetail;

        // Sort pages strictly once on load
        const sortedPages = [...(rawDoc.pages || [])].sort((a, b) => a.page_number - b.page_number);
        setDocument({ ...rawDoc, pages: sortedPages });

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        let token = "";
        if (typeof window !== "undefined") {
          token = getAccessToken() || getSession()?.token || "";
        }

        if (token) {
          setFileUrl(`${apiUrl}/documents/${documentId}/file?token=${token}`);
        } else {
          setFileError("Non autorisé. Veuillez vous reconnecter.");
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Impossible de charger le document.",
        );
      } finally {
        setLoading(false);
      }
    }

    loadDocument();
  }, [documentId]);

  // Scroll to evidence mark when document and evidence are ready
  useEffect(() => {
    if (!document || evidenceItems.length === 0) return;

    const timer = setTimeout(() => {
      const markEl = window.document.getElementById("evidence-0");
      if (markEl) {
        markEl.scrollIntoView({ behavior: "smooth", block: "center" });
      } else if (evidenceItems[0]?.page_number) {
        const pageEl = window.document.getElementById(`page-${evidenceItems[0].page_number}`);
        if (pageEl) {
          pageEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [document, evidenceItems]);

  // Keep sidebar page centered on current active page
  useEffect(() => {
    if (typeof window === "undefined") return;
    const activeBtn = window.document.getElementById(`sidebar-page-${currentPage}`);
    if (activeBtn) {
      activeBtn.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [currentPage]);

  const activeEvidence = evidenceItems.length > 0 ? evidenceItems[0] : null;
  const isPdf = document?.file_type === "pdf";

  // Sidebar page click handler
  const handlePageClick = (pageNumber: number) => {
    setCurrentPage(pageNumber);
    setNonce((n) => n + 1);

    if (!isPdf) {
      const el = window.document.getElementById(`page-${pageNumber}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  };

  // "Aller au passage" button handler
  const goToEvidence = () => {
    if (!activeEvidence) return;
    setCurrentPage(activeEvidence.page_number);
    setNonce((n) => n + 1);

    if (!isPdf) {
      const markEl = window.document.getElementById("evidence-0");
      if (markEl) {
        markEl.scrollIntoView({ behavior: "smooth", block: "center" });
      } else {
        const pageEl = window.document.getElementById(`page-${activeEvidence.page_number}`);
        if (pageEl) {
          pageEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    }
  };

  return (
    <AuthGuard>
      <div>
        {/* Loading */}
        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-xs">
            <div className="h-8 w-8 mx-auto rounded-full border-2 border-camrail-red border-t-transparent animate-spin mb-3"></div>
            <p className="text-sm font-medium text-slate-500">Chargement du document...</p>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-sm font-semibold text-red-700">Impossible de charger le document</p>
            <p className="mt-2 text-xs text-red-600">{error}</p>
            <Link
              href="/documents"
              className="mt-4 inline-flex rounded-xl bg-camrail-red px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-700 transition"
            >
              Retour aux documents
            </Link>
          </div>
        )}

        {/* Document */}
        {!loading && !error && document && (
          <>
            {/* Header */}
            <div className="mb-6">
              <Link
                href="/documents"
                className="text-sm font-semibold text-camrail-red transition hover:text-red-700 flex items-center gap-1.5"
              >
                <span>←</span> Retour aux documents
              </Link>

              <div className="mt-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Document #{document.id}
                  </p>
                  <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
                    {document.title}
                  </h1>
                  <p className="mt-1 text-sm text-slate-600 font-medium">
                    Version {document.version} • {document.pages.length} {document.pages.length > 1 ? "pages" : "page"} • {document.department}
                  </p>
                </div>
              </div>
            </div>

            {/* Fixed Evidence Banner if evidence available */}
            {activeEvidence && (
              <div className="sticky top-2 z-20 mb-4 rounded-xl border border-amber-300 bg-amber-50/95 p-4 shadow-md backdrop-blur-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-bold bg-amber-200 text-amber-900 shadow-xs">
                      Passage utilisé par l&apos;IA — Page {activeEvidence.page_number}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-amber-950 font-sans italic leading-relaxed bg-white/85 p-3 rounded-lg border border-amber-200/70 select-text">
                    &ldquo;{activeEvidence.text}&rdquo;
                  </p>
                </div>
                <button
                  type="button"
                  onClick={goToEvidence}
                  className="shrink-0 inline-flex items-center gap-1.5 px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-amber-600 cursor-pointer"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                  Aller au passage
                </button>
              </div>
            )}

            {/* Viewer layout */}
            <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
              {/* Page navigation sidebar */}
              <aside className="hidden lg:block">
                <div className="sticky top-5 rounded-2xl border border-slate-200 bg-white p-3 max-h-[80vh] overflow-y-auto shadow-xs">
                  <p className="px-2 pb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
                    Pages ({document.pages.length})
                  </p>

                  <div className="space-y-1">
                    {document.pages.map((page) => {
                      const isActive = currentPage === page.page_number;
                      return (
                        <button
                          key={page.id}
                          id={`sidebar-page-${page.page_number}`}
                          type="button"
                          onClick={() => handlePageClick(page.page_number)}
                          className={`w-full flex items-center justify-between rounded-lg px-3 py-2 text-sm transition text-left cursor-pointer ${
                            isActive
                              ? "bg-red-50 text-camrail-red font-semibold border-l-[3px] border-camrail-red pl-2.5 shadow-xs"
                              : "text-slate-600 hover:bg-slate-50 hover:text-camrail-red border-l-[3px] border-transparent pl-2.5"
                          }`}
                        >
                          <span>Page {page.page_number}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </aside>

              {/* Document File Viewer */}
              <section
                className="rounded-2xl border border-slate-200 bg-slate-100 p-3 sm:p-5 h-[800px] flex flex-col relative overflow-hidden"
                onContextMenu={(e) => e.preventDefault()}
              >
                {/* Filigrane de sécurité anti-capture discret (fond strict, opacité <= 0.05, jamais au-dessus du texte) */}
                <div
                  aria-hidden="true"
                  className="absolute inset-0 pointer-events-none -z-10 select-none flex items-center justify-center opacity-[0.03] overflow-hidden"
                >
                  <div className="transform -rotate-45 text-2xl sm:text-3xl font-black text-slate-900 tracking-[0.25em] whitespace-nowrap">
                    CAMRAIL CONFIDENTIEL • USAGE INTERNE
                  </div>
                </div>

                <div className="flex-1 w-full h-full bg-white rounded-xl overflow-hidden shadow-inner relative z-0">
                  {fileUrl && isPdf ? (
                    /* PDF Mode */
                    <iframe
                      key={`${currentPage}-${nonce}`}
                      src={`${fileUrl}#page=${currentPage}&toolbar=0&navpanes=0`}
                      className="w-full h-full border-0"
                      title="Visionneuse de document PDF"
                    />
                  ) : fileUrl ? (
                    /* DOCX / Text Page-by-page Mode */
                    <div className="p-6 sm:p-10 overflow-y-auto h-full text-slate-800 bg-white">
                      <div className="max-w-3xl mx-auto space-y-12">
                        {document.pages.map((page) => {
                          const text = page.extracted_text || "Aucun texte extrait pour cette page.";

                          // Find any evidence matching this specific page
                          const matchingEvidences = evidenceItems.filter(
                            (e) => e.page_number === page.page_number
                          );

                          let processedText = text;
                          let evidenceNotFoundNotice = false;

                          if (matchingEvidences.length > 0) {
                            const ev = matchingEvidences[0];
                            const match = findNormalized(text, ev.text);

                            if (match) {
                              const before = text.slice(0, match.start);
                              const target = text.slice(match.start, match.end);
                              const after = text.slice(match.end);

                              processedText = `${before}<mark id="evidence-0" class="bg-amber-200 text-slate-900 px-1 py-0.5 rounded shadow-xs font-semibold ring-2 ring-amber-400">${target}</mark>${after}`;
                            } else {
                              evidenceNotFoundNotice = true;
                            }
                          }

                          return (
                            <div
                              key={page.id}
                              id={`page-${page.page_number}`}
                              className="scroll-mt-16 border-b border-slate-100 pb-8 last:border-b-0"
                            >
                              <div className="flex items-center justify-between mb-4 border-b border-slate-200 pb-2">
                                <h3 className="text-base font-bold text-slate-900">
                                  Page {page.page_number}
                                </h3>
                                {matchingEvidences.length > 0 && (
                                  <span className="text-xs font-semibold px-2 py-0.5 bg-amber-100 text-amber-800 rounded">
                                    Contient la preuve IA
                                  </span>
                                )}
                              </div>

                              <div className="font-sans text-base leading-[1.7] text-slate-800 bg-white p-6 rounded-xl border border-slate-200 max-w-[70ch] shadow-xs">
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                  rehypePlugins={[rehypeRaw]}
                                  components={{
                                    table: ({ children }) => (
                                      <div className="overflow-x-auto my-4 rounded-lg border border-slate-200 shadow-xs">
                                        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                                          {children}
                                        </table>
                                      </div>
                                    ),
                                    thead: ({ children }) => (
                                      <thead className="bg-slate-100 font-semibold text-slate-800">
                                        {children}
                                      </thead>
                                    ),
                                    tbody: ({ children }) => (
                                      <tbody className="divide-y divide-slate-100 bg-white">
                                        {children}
                                      </tbody>
                                    ),
                                    tr: ({ children, ...props }) => (
                                      <tr className="even:bg-slate-50/60 hover:bg-slate-50 transition-colors" {...props}>
                                        {children}
                                      </tr>
                                    ),
                                    th: ({ children }) => (
                                      <th className="px-4 py-2.5 text-xs font-bold text-slate-700 uppercase tracking-wider">
                                        {children}
                                      </th>
                                    ),
                                    td: ({ children }) => (
                                      <td className="px-4 py-2.5 text-sm text-slate-800 whitespace-normal">
                                        {children}
                                      </td>
                                    ),
                                    p: ({ children }) => (
                                      <p className="mb-3 text-base leading-[1.7] text-slate-800 last:mb-0">
                                        {children}
                                      </p>
                                    ),
                                  }}
                                >
                                  {processedText}
                                </ReactMarkdown>
                              </div>

                              {evidenceNotFoundNotice && (
                                <p className="mt-2 text-xs text-slate-500 italic">
                                  Note : La phrase de preuve se situe sur cette page mais n&apos;a pas pu être surlignée mot à mot.
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center w-full h-full text-slate-400 flex-col gap-3">
                      {loading ? (
                        <p className="text-sm">Chargement du document...</p>
                      ) : (
                        <div className="text-center p-6">
                          <p className="text-sm font-medium text-slate-600">Impossible d&apos;afficher le document original.</p>
                          {fileError && <p className="text-xs text-red-500 mt-2 font-medium">Détail : {fileError}</p>}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </section>
            </div>
          </>
        )}
      </div>
    </AuthGuard>
  );
}
