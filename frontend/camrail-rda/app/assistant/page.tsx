"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch, ApiError } from "@/lib/api";
import type { BackendCitation, AssistantResponse } from "@/lib/backend-types";
import ReactMarkdown from "react-markdown";

type Citation = BackendCitation;

type Message = {
  role: "user" | "assistant";
  content: string;
  confidence?: "high" | "medium" | "insufficient";
  citations?: Citation[];
  abstention?: boolean;
};

const confidenceConfig = {
  high: {
    label: "Confiance élevée",
    className: "bg-emerald-100 text-emerald-800 border-emerald-200",
  },
  medium: {
    label: "Confiance moyenne",
    className: "bg-amber-100 text-amber-800 border-amber-200",
  },
  insufficient: {
    label: "Information insuffisante",
    className: "bg-red-100 text-red-800 border-red-200",
  },
};

function AssistantContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const cParam = searchParams.get("c");

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load chat history from server if param c exists, else use sessionStorage
  useEffect(() => {
    if (cParam) {
      const cid = parseInt(cParam, 10);
      setConversationId(cid);
      setLoading(true);
      apiFetch(`/assistant/conversations/${cid}/messages`)
        .then((data: any) => {
          if (Array.isArray(data)) {
            setMessages(data.map((m: any) => ({
              role: m.role,
              content: m.content,
              citations: m.citations || [],
              confidence: m.role === 'assistant' ? 'medium' : undefined // Basic fallback for UI
            })));
          }
        })
        .catch((err) => {
          console.error(err);
          // If conversation is not found (e.g., deleted), clear the URL param
          if (err.status === 404) {
            router.replace("/assistant");
          }
        })
        .finally(() => {
          setLoading(false);
          setIsLoaded(true);
        });
    } else {
      const saved = sessionStorage.getItem("railmind_chat_messages");
      const savedConvId = sessionStorage.getItem("railmind_conversation_id");
      
      if (saved) {
        try {
          setMessages(JSON.parse(saved));
        } catch (e) {
          console.error("Failed to parse saved messages");
        }
      }
      
      if (savedConvId) {
        setConversationId(parseInt(savedConvId, 10));
      }
      
      setIsLoaded(true);
    }
  }, [cParam]);

  // Save chat history to sessionStorage when it changes
  useEffect(() => {
    if (isLoaded) {
      sessionStorage.setItem("railmind_chat_messages", JSON.stringify(messages));
      if (conversationId) {
        sessionStorage.setItem("railmind_conversation_id", conversationId.toString());
      }
    }
  }, [messages, conversationId, isLoaded]);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Focus input on load
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function handleSubmit(e?: FormEvent<HTMLFormElement>) {
    e?.preventDefault();
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) return;

    setMessages((current) => [...current, { role: "user", content: trimmedQuestion }]);
    setQuestion("");
    setLoading(true);

    try {
      const payload: any = { query: trimmedQuestion };
      if (conversationId) {
        payload.conversation_id = conversationId;
      }
      
      const data = (await apiFetch("/assistant/query", {
        method: "POST",
        body: JSON.stringify(payload),
      })) as AssistantResponse & { conversation_id?: number };
      
      if (data.conversation_id && !conversationId) {
        setConversationId(data.conversation_id);
        window.dispatchEvent(new Event("reload-conversations"));
        router.replace(`?c=${data.conversation_id}`);
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer,
          confidence: data.confidence,
          citations: data.citations ?? [],
          abstention: data.confidence === "insufficient",
        },
      ]);
    } catch (error) {
      if (error instanceof ApiError) {
        const msg = error.body?.detail || error.message || "Erreur serveur";
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: `Impossible d'effectuer la recherche : ${msg}`,
            confidence: "insufficient",
            abstention: true,
          },
        ]);
      } else {
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: "Une erreur est survenue lors de la recherche documentaire.",
            confidence: "insufficient",
            abstention: true,
          },
        ]);
      }
    } finally {
      setLoading(false);
      // Give focus back to input
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <AuthGuard>
      <div className="flex flex-col h-[calc(100vh-64px)] relative">
        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto pb-32">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full px-4 text-center mt-10 md:mt-20">
              <img src="/camrail-logo.png" alt="CAMRAIL Logo" className="h-12 w-auto object-contain mb-6" />
              <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">RailMind Lite</h2>
              <p className="text-slate-500 mb-6 text-sm md:text-base font-medium">Votre assistant documentaire CAMRAIL</p>
              
              <p className="text-sm text-slate-600 mb-8 max-w-md">
                Posez une question sur les documents techniques, les procédures ou les règles disponibles.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl w-full">
                {[
                  "En quoi consiste la maintenance préventive selon les procédures ?",
                  "Quel est le rôle principal de la signalisation ferroviaire ?",
                  "À quelle vitesse un train est-il qualifié de grande vitesse ?",
                  "Quel est le rôle de l'EPSF en matière de sécurité ?"
                ].map((suggestion, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setQuestion(suggestion);
                      setTimeout(() => inputRef.current?.focus(), 10);
                    }}
                    className="p-4 border border-slate-200 rounded-xl text-left hover:border-camrail-red hover:shadow-md transition-all text-sm text-slate-600 bg-white"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto w-full px-4 pt-6 pb-6 space-y-6">
              {messages.map((message, index) => (
                <div key={index} className={`flex gap-4 p-5 rounded-xl ${message.role === "user" ? "bg-slate-50" : "bg-white"}`}>
                  {message.role === "assistant" ? (
                    <div className="shrink-0 h-8 w-8 flex items-center justify-center bg-white border border-slate-100 rounded-full shadow-sm">
                      <img src="/camrail-logo.png" alt="RailMind" className="h-4 w-auto object-contain" />
                    </div>
                  ) : (
                    <div className="shrink-0 h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-bold text-xs mt-1">
                      U
                    </div>
                  )}
                  
                  <div className="flex-1 min-w-0 flex flex-col items-start">
                    {/* Main Content */}
                    <div className={`w-full ${message.abstention ? "p-4 bg-red-50 border border-red-100 rounded-xl text-slate-800" : "text-slate-800"}`}>
                      {message.role === "assistant" ? (
                        <div className="prose prose-sm prose-slate max-w-none leading-relaxed">
                          <ReactMarkdown>{message.content}</ReactMarkdown>
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed font-medium">{message.content}</p>
                      )}
                    </div>

                    {/* Assistant Metadata (Confidence & Citations) */}
                    {message.role === "assistant" && (
                      <div className="w-full mt-4 space-y-5">
                        {/* Confidence Badge */}
                        {message.confidence && (
                          <div className="flex items-center gap-2">
                            <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold border ${confidenceConfig[message.confidence].className}`}>
                              {message.abstention ? "⚠ " : ""}{confidenceConfig[message.confidence].label}
                            </span>
                          </div>
                        )}

                        {/* Citations Cards */}
                        {message.citations && message.citations.length > 0 && (
                          <div className="mt-4 pt-4 border-t border-slate-100">
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Sources utilisées ({message.citations.length})</p>
                            <div className="flex flex-wrap gap-3">
                              {message.citations.map((cit, idx) => (
                                <Link 
                                  key={idx}
                                  href={`/documents/${cit.document_id}#page=${cit.page_start}&search=${encodeURIComponent((cit.excerpt.length > 50 ? cit.excerpt.substring(Math.floor(cit.excerpt.length/2) - 25, Math.floor(cit.excerpt.length/2) + 25) : cit.excerpt).replace(/\n/g, ' ').trim())}&words=${encodeURIComponent(message.content.replace(/\n/g, ' ').trim())}`}
                                  className="group flex flex-col p-4 rounded-xl border border-slate-200 bg-white hover:border-camrail-red hover:shadow-sm transition-all w-64"
                                >
                                  <div className="mb-1">
                                    <span className="text-xs text-camrail-red font-bold uppercase tracking-wider">Source {idx + 1}</span>
                                  </div>
                                  <h4 className="text-sm font-semibold text-slate-800 truncate group-hover:text-camrail-red mb-2">
                                    {cit.document_title}
                                  </h4>
                                  <div className="flex flex-col gap-1 text-xs text-slate-500">
                                    {cit.document_version && <span>Version {cit.document_version}</span>}
                                    {cit.page_start > 0 && <span>Page {cit.page_start}</span>}
                                  </div>
                                </Link>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Loading State */}
              {loading && (
                <div className="flex gap-4 p-5 rounded-xl bg-white">
                  <div className="shrink-0 h-8 w-8 flex items-center justify-center bg-white border border-slate-100 rounded-full shadow-sm animate-pulse">
                    <img src="/camrail-logo.png" alt="RailMind" className="h-4 w-auto object-contain" />
                  </div>
                  <div className="flex flex-col items-start mt-1.5">
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1">
                        <span className="h-2 w-2 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                        <span className="h-2 w-2 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                        <span className="h-2 w-2 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                      </div>
                      <span className="text-sm text-slate-500 font-medium">Recherche dans les documents...</span>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} className="h-4" />
            </div>
          )}
        </div>

        {/* Sticky Input Area */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-slate-50 via-slate-50 to-transparent pt-10 pb-6 px-4">
          <div className="max-w-3xl mx-auto">
            <form 
              onSubmit={handleSubmit}
              className="relative rounded-2xl border border-slate-300 bg-white shadow-lg overflow-hidden focus-within:border-camrail-red focus-within:ring-1 focus-within:ring-camrail-red transition-all"
            >
              <textarea
                ref={inputRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Posez votre question à RailMind Lite..."
                className="w-full resize-none bg-transparent py-4 pl-4 pr-14 text-sm text-slate-900 placeholder-slate-400 focus:outline-none min-h-[60px] max-h-[200px]"
                rows={Math.min(5, Math.max(1, question.split('\n').length))}
                disabled={loading}
              />
              <button
                type="submit"
                disabled={!question.trim() || loading}
                className="absolute right-2 bottom-2 rounded-xl p-2.5 text-white bg-camrail-red hover:bg-camrail-red-dark disabled:bg-slate-200 disabled:text-slate-400 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
              </button>
            </form>
            <p className="text-center text-xs text-slate-400 mt-3">
              RailMind Lite peut faire des erreurs. Vérifiez toujours les documents sources.
            </p>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}

export default function AssistantPage() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center">Chargement...</div>}>
      <AssistantContent />
    </Suspense>
  );
}