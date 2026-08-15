
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch } from "@/lib/api";
import { getAccessToken, getSession } from "@/lib/auth";

type DocumentPage = {
  id: string;
  page_number: number;
  extracted_text: string;
  extraction_method: string;
};

type DocumentDetail = {
  id: string;
  title: string;
  category: string;
  department: string;
  version: string;
  status: "processing" | "indexed" | "active" | "failed";
  checksum: string;
  uploaded_by: string;
  created_at: string;
  pages: DocumentPage[];
};

export default function DocumentViewerPage() {
  const params = useParams();
  const documentId = String(params.id);

  const [document, setDocument] =
    useState<DocumentDetail | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fileError, setFileError] = useState("");
  const [urlHash, setUrlHash] = useState<string>("");
  const [fileUrl, setFileUrl] = useState<string | null>(null);

  useEffect(() => {
    async function loadDocument() {
      try {
        setLoading(true);
        setError("");

        const data = await apiFetch(
          `/documents/${documentId}`,
        );

        setDocument(data as DocumentDetail);

        // Set direct file URL to avoid Blob limitations and enable native PDF highlighting
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

        // We don't extract page number manually anymore, we pass the raw hash to the iframe.
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

  useEffect(() => {
    if (typeof window !== "undefined") {
      setUrlHash(window.location.hash);
      const handleHashChange = () => setUrlHash(window.location.hash);
      window.addEventListener("hashchange", handleHashChange);
      return () => window.removeEventListener("hashchange", handleHashChange);
    }
  }, []);

  return (
    <AuthGuard>
      <div>
        {/* Loading */}
        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center">
            <p className="text-sm text-slate-500">
              Chargement du document...
            </p>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-sm font-semibold text-red-700">
              Impossible de charger le document
            </p>

            <p className="mt-2 text-xs text-red-600">
              {error}
            </p>

            <Link
              href="/documents"
              className="mt-4 inline-flex rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-700"
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
                className="text-sm font-semibold text-red-600 transition hover:text-red-700"
              >
                ← Retour aux documents
              </Link>

              <div className="mt-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Document · {document.id}
                  </p>

                  <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-950">
                    {document.title}
                  </h1>

                  <p className="mt-1 text-sm text-slate-500">
                    Version {document.version} ·{" "}
                    {document.pages.length} pages ·{" "}
                    {document.department}
                  </p>
                </div>
                {/* Téléchargement désactivé pour des raisons de sécurité (fuite de données) */}
              </div>
            </div>

            {/* Viewer */}
            <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
              {/* Page navigation */}
              <aside className="hidden lg:block">
                <div className="sticky top-5 rounded-2xl border border-slate-200 bg-white p-3">
                  <p className="px-2 pb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Pages
                  </p>

                  <div className="space-y-1">
                    {document.pages.map((page) => (
                      <a
                        key={page.id}
                        href={`#page=${page.page_number}`}
                        className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 hover:text-red-600"
                      >
                        <span>
                          Page {page.page_number}
                        </span>
                      </a>
                    ))}
                  </div>
                </div>
              </aside>

              {/* Document File Viewer */}
              <section className="rounded-2xl border border-slate-200 bg-slate-100 p-3 sm:p-5 h-[800px] flex flex-col relative" onContextMenu={(e) => e.preventDefault()}>
                {/* Filigrane de sécurité anti-capture */}
                <div className="absolute inset-0 pointer-events-none z-10 flex items-center justify-center opacity-5 overflow-hidden">
                   <div className="transform -rotate-45 text-4xl font-black text-black tracking-widest whitespace-pre">
                      CONFIDENTIEL CAMRAIL   CONFIDENTIEL CAMRAIL   CONFIDENTIEL CAMRAIL
                   </div>
                </div>
                
                <div className="flex-1 w-full h-full bg-white rounded-xl overflow-hidden shadow-inner relative z-0">
                  {fileUrl && document.title.toLowerCase().endsWith('.pdf') ? (
                    <iframe src={`${fileUrl}${urlHash ? urlHash + '&toolbar=0&navpanes=0' : '#toolbar=0&navpanes=0'}`} className="w-full h-full border-0" title="Visionneuse de document" />
                  ) : fileUrl ? (
                    <div className="p-6 sm:p-10 overflow-y-auto h-full text-slate-700 bg-white">
                      <div className="max-w-3xl mx-auto space-y-12">
                        {document.pages.sort((a, b) => a.page_number - b.page_number).map((page) => {
                          const wordsMatch = urlHash.match(/words=([^&]*)/);
                          const wordsParam = wordsMatch ? decodeURIComponent(wordsMatch[1]) : "";
                          let text = page.extracted_text || "Aucun texte extrait pour cette page.";
                          
                          // Liste des petits mots de liaison à ignorer pour éviter de surligner tout le document
                          const stopWords = new Set(["les", "une", "des", "aux", "est", "sont", "qui", "que", "quoi", "dont", "par", "sur", "ils", "ces", "ses", "son"]);
                          
                          // Extraire TOUS les mots de la réponse IA (qui a été passée dans words=)
                          // Contrainte : uniquement les mots de 3 caractères ou plus
                          const wordsToHighlight = wordsParam
                            .replace(/[^\wÀ-ÿ\d]/g, ' ')
                            .split(' ')
                            .map(w => w.trim().toLowerCase())
                            .filter(w => w.length >= 3 && !stopWords.has(w));
                            
                          // Fonction pour surligner les mots
                          const renderHighlightedText = (content: string) => {
                            if (wordsToHighlight.length === 0) return content;
                            
                            // Créer une regex qui match n'importe quel mot de la liste
                            // On trie par longueur décroissante pour éviter qu'un mot court (ex: "rail") empêche le match d'un mot long (ex: "camrail")
                            const sortedWords = [...new Set(wordsToHighlight)].sort((a, b) => b.length - a.length);
                            const regex = new RegExp(`\\b(${sortedWords.join('|')})\\b`, 'gi');
                            const parts = content.split(regex);
                            
                            return parts.map((part, i) => {
                              if (sortedWords.includes(part.toLowerCase())) {
                                return <mark key={i} className="bg-yellow-300 text-black px-1 rounded shadow-sm font-bold">{part}</mark>;
                              }
                              return part;
                            });
                          };
                          
                          return (
                            <div key={page.id} id={`page=${page.page_number}`} className="scroll-mt-10">
                              <h3 className="text-lg font-bold text-slate-800 mb-4 border-b border-slate-200 pb-2">Page {page.page_number}</h3>
                              <div className="prose prose-slate prose-sm max-w-none whitespace-pre-wrap font-mono text-xs text-slate-600 bg-slate-50 p-4 rounded-lg border border-slate-100">
                                {renderHighlightedText(text)}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center w-full h-full text-slate-400 flex-col gap-3">
                      {loading ? (
                        <p>Chargement du document...</p>
                      ) : (
                        <div>
                          <p>Impossible d'afficher le document original.</p>
                          {fileError && <p className="text-xs text-red-500 mt-2">Détail : {fileError}</p>}
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

