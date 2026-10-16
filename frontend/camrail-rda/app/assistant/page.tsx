"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch, ApiError } from "@/lib/api";
import { getSession, getUserFirstName, getAccessToken } from "@/lib/auth";
import type { BackendCitation, AssistantResponse } from "@/lib/backend-types";
import ReactMarkdown from "react-markdown";
import { useLanguage } from "@/lib/LanguageContext";
import { SUGGESTED_QUESTIONS } from "@/lib/suggestions";
import { formatConfidence, getConfidenceDescription } from "@/lib/labels";
import { Skeleton } from "@/components/ui/skeleton";

type Citation = BackendCitation;

type Message = {
  role: "user" | "assistant";
  content: string;
  confidence?: "high" | "medium" | "insufficient";
  citations?: Citation[];
  abstention?: boolean;
};

function AssistantContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const cParam = searchParams.get("c");

  const { language, t } = useLanguage();

  const handleViewInDocument = (cit: Citation) => {
    if (!cit.document_id) return;
    const targetPage = cit.evidence && cit.evidence.length > 0
      ? cit.evidence[0].page_number
      : (cit.page_start || 1);

    const evidencePayload = {
      savedAt: Date.now(),
      items: cit.evidence && cit.evidence.length > 0
        ? cit.evidence.map(e => ({ page_number: e.page_number, text: e.text }))
        : [{ page_number: targetPage, text: cit.excerpt }]
    };

    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(`evidence:${cit.document_id}`, JSON.stringify(evidencePayload));
      } catch (e) {
        console.error("Erreur lors de la sauvegarde de l'evidence dans localStorage:", e);
      }
    }

    router.push(`/documents/${cit.document_id}?page=${targetPage}&ev=0`);
  };

  const confidenceConfig = {
    high: {
      label: language === "fr" ? "Confiance Élevée" : "High confidence",
      className: "bg-emerald-50 text-emerald-800 border-emerald-200",
    },
    medium: {
      label: language === "fr" ? "Confiance moyenne" : "Medium confidence",
      className: "bg-amber-50 text-amber-800 border-amber-200",
    },
    insufficient: {
      label: language === "fr" ? "Information insuffisante" : "Insufficient information",
      className: "bg-red-50 text-red-800 border-red-200",
    },
  };

  const [userName, setUserName] = useState<string>("");
  const [docCount, setDocCount] = useState<number | null>(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [streamingStatus, setStreamingStatus] = useState<"idle" | "searching" | "drafting">("idle");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isListening, setIsListening] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load user name and doc count
  useEffect(() => {
    const session = getSession();
    if (session?.email) {
      setUserName(getUserFirstName(session.email));
    }
    apiFetch("/documents")
      .then((data: any) => {
        if (Array.isArray(data)) {
          setDocCount(data.length);
        }
      })
      .catch(() => {});
  }, []);

  // Initialize Speech Recognition
  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        recognitionRef.current = new SpeechRecognition();
        recognitionRef.current.continuous = false;
        recognitionRef.current.interimResults = false;
        
        recognitionRef.current.onresult = (event: any) => {
          const transcript = event.results[0][0].transcript;
          setQuestion(transcript);
          setTimeout(() => {
            const formEvent = new Event('submit', { cancelable: true }) as any;
            handleSubmit(formEvent, transcript);
          }, 300);
        };

        recognitionRef.current.onerror = (event: any) => {
          console.error("Speech recognition error", event.error);
          setIsListening(false);
        };

        recognitionRef.current.onend = () => {
          setIsListening(false);
        };
      }
    }
  }, []);

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
    } else {
      if (recognitionRef.current) {
        recognitionRef.current.lang = language === 'fr' ? 'fr-FR' : 'en-US';
        recognitionRef.current.start();
        setIsListening(true);
      } else {
        alert("La reconnaissance vocale n'est pas supportée par votre navigateur.");
      }
    }
  };

  const handleSpeak = (text: string) => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        return;
      }
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = language === 'fr' ? 'fr-FR' : 'en-US';
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
    setStreamingStatus("idle");
  };

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
              confidence: m.confidence || (m.role === 'assistant' ? 'medium' : undefined)
            })));
          }
        })
        .catch((err) => {
          console.error(err);
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

  // Translate existing messages when language changes
  const [translatingLanguage, setTranslatingLanguage] = useState(false);
  const previousLanguageRef = useRef(language);

  useEffect(() => {
    if (isLoaded && messages.length > 0 && language !== previousLanguageRef.current) {
      previousLanguageRef.current = language;
      
      const translateCurrentChat = async () => {
        setTranslatingLanguage(true);
        try {
          const payload = {
            messages: messages.map(m => ({ role: m.role, content: m.content })),
            target_language: language === 'fr' ? 'français' : 'english'
          };
          
          const data = await apiFetch("/assistant/translate", {
            method: "POST",
            body: JSON.stringify(payload)
          });
          
          if (data && data.translated_messages && data.translated_messages.length === messages.length) {
            setMessages(current => current.map((m, idx) => ({
              ...m,
              content: data.translated_messages[idx]
            })));
          }
        } catch (error) {
          console.error("Failed to translate messages", error);
        } finally {
          setTranslatingLanguage(false);
        }
      };

      translateCurrentChat();
    }
  }, [language, isLoaded]);

  // Sync to sessionStorage
  useEffect(() => {
    if (isLoaded && !cParam && messages.length > 0) {
      sessionStorage.setItem("railmind_chat_messages", JSON.stringify(messages));
      if (conversationId) {
        sessionStorage.setItem("railmind_conversation_id", conversationId.toString());
      }
    }
  }, [messages, conversationId, isLoaded, cParam]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, streamingStatus]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function handleSubmit(e?: any, forcedQuestion?: string) {
    e?.preventDefault();
    const textToSubmit = forcedQuestion || question;
    const trimmedQuestion = textToSubmit.trim();

    if (!trimmedQuestion || loading) return;

    setMessages((current) => [...current, { role: "user", content: trimmedQuestion }]);
    if (!forcedQuestion) setQuestion("");
    setLoading(true);
    setStreamingStatus("searching");

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Ajouter un message assistant vide pour accueillir les tokens au fil de l'eau
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        content: "",
        citations: [],
        confidence: undefined,
        abstention: false
      }
    ]);

    try {
      const token = getAccessToken() || (typeof window !== "undefined" ? localStorage.getItem("token") : null);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const payload: any = { query: trimmedQuestion, language: language };
      if (conversationId) {
        payload.conversation_id = conversationId;
      }

      const response = await fetch(`${apiUrl}/api/v1/assistant/query/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error(language === 'fr' ? "Trop de requêtes, veuillez patienter une minute." : "Too many requests, please wait a minute.");
        }
        if (response.status === 503) {
          throw new Error(language === 'fr' ? "Le serveur est très sollicité, réessayez dans un instant." : "The server is busy, please retry in a moment.");
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Stream body is null");

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            currentEvent = "";
            continue;
          }
          if (trimmed.startsWith("event:")) {
            currentEvent = trimmed.slice(6).trim();
          } else if (trimmed.startsWith("data:")) {
            const dataStr = trimmed.slice(5).trim();
            try {
              const data = JSON.parse(dataStr);
              if (currentEvent === "sources") {
                setStreamingStatus("drafting");
                if (data.conversation_id && !conversationId) {
                  setConversationId(data.conversation_id);
                  window.dispatchEvent(new Event("reload-conversations"));
                  router.replace(`?c=${data.conversation_id}`);
                }
                setMessages((current) => {
                  const updated = [...current];
                  const last = updated[updated.length - 1];
                  if (last && last.role === "assistant") {
                    last.citations = data.sources || [];
                    last.confidence = data.confidence;
                  }
                  return updated;
                });
              } else if (currentEvent === "token") {
                setStreamingStatus("drafting");
                const tokenText = data.token || "";
                setMessages((current) => {
                  const updated = [...current];
                  const last = updated[updated.length - 1];
                  if (last && last.role === "assistant") {
                    last.content += tokenText;
                  }
                  return updated;
                });
              } else if (currentEvent === "done") {
                setStreamingStatus("idle");
                setMessages((current) => {
                  const updated = [...current];
                  const last = updated[updated.length - 1];
                  if (last && last.role === "assistant") {
                    last.content = data.answer || last.content;
                    last.citations = data.citations || last.citations;
                    last.confidence = data.confidence || last.confidence;
                    last.abstention = data.confidence === "insufficient";
                  }
                  return updated;
                });
              } else if (currentEvent === "error") {
                throw new Error(data.detail || "Erreur de génération");
              }
            } catch (err: any) {
              if (currentEvent === "error") throw err;
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === "AbortError") {
        console.log("Génération interrompue par l'utilisateur.");
        return;
      }
      setMessages((current) => {
        const updated = [...current];
        const last = updated[updated.length - 1];
        if (last && last.role === "assistant" && !last.content) {
          last.content = language === 'fr' 
            ? `Impossible d'effectuer la recherche : ${error.message || "Erreur serveur"}` 
            : `Unable to perform search: ${error.message || "Server error"}`;
          last.confidence = "insufficient";
          last.abstention = true;
        }
        return updated;
      });
    } finally {
      setLoading(false);
      setStreamingStatus("idle");
      abortControllerRef.current = null;
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Convertit les marqueurs [n] ou [source n] en liens/boutons cliquables dans le texte
  const renderFormattedMarkdown = (content: string, citations?: Citation[]) => {
    const formatted = content.replace(/\[(?:source\s*)?(\d+)\]/gi, (match, p1) => {
      return `[${match}](#source-${p1})`;
    });

    return (
      <ReactMarkdown
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#source-")) {
              const idxStr = href.replace("#source-", "");
              const idx = parseInt(idxStr, 10);
              return (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    const card = document.getElementById(`source-card-${idx}`);
                    if (card) {
                      card.scrollIntoView({ behavior: "smooth", block: "center" });
                      card.classList.add("ring-2", "ring-camrail-red", "bg-red-50");
                      setTimeout(() => card.classList.remove("ring-2", "ring-camrail-red", "bg-red-50"), 2000);
                    }
                    if (citations && citations[idx - 1]) {
                      handleViewInDocument(citations[idx - 1]);
                    }
                  }}
                  className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-red-100 hover:bg-camrail-red text-camrail-red hover:text-white font-sans text-xs font-semibold transition-all cursor-pointer shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red"
                  title={`Consulter la source ${idx}`}
                >
                  {children}
                </button>
              );
            }
            return <a href={href} target="_blank" rel="noopener noreferrer" className="text-camrail-red underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red rounded">{children}</a>;
          }
        }}
      >
        {formatted}
      </ReactMarkdown>
    );
  };

  return (
    <AuthGuard>
      <div className="flex flex-col h-[calc(100vh-64px)] relative">
        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto pb-40">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full px-4 text-center mt-8 md:mt-16 max-w-3xl mx-auto">
              <span className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-camrail-red border border-red-200/80 mb-5 shadow-2xs">
                <span className="h-2 w-2 rounded-full bg-camrail-red animate-pulse"></span>
                {t("assistant.docs_available", { count: docCount ?? 28 })}
              </span>

              <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-slate-900 mb-2">
                {userName
                  ? t("assistant.greeting_named", { name: userName })
                  : t("assistant.greeting_default")}
              </h2>
              <p className="text-slate-600 mb-8 text-sm md:text-base font-medium max-w-xl">
                {t("assistant.subtitle")}
              </p>
              
              <div className="w-full text-left mb-3">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-600 px-1">
                  {t("assistant.suggested_title")}
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 w-full">
                {SUGGESTED_QUESTIONS.map((item) => {
                  const qText = item.question[language] || item.question.fr;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        setQuestion(qText);
                        setTimeout(() => inputRef.current?.focus(), 50);
                      }}
                      className="group flex flex-col items-start p-4 border border-slate-200 rounded-xl text-left hover:border-camrail-red hover:shadow-sm transition-all cursor-pointer bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red"
                    >
                      <span className="text-[11px] font-bold text-camrail-red uppercase tracking-wider mb-1.5">
                        {item.category}
                      </span>
                      <span className="text-sm font-medium text-slate-800 group-hover:text-camrail-red transition-colors leading-snug">
                        {qText}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto w-full px-4 pt-6 pb-6 space-y-6">
              {messages.map((message, index) => (
                <div key={index} className={`flex gap-4 p-5 rounded-xl ${message.role === "user" ? "bg-slate-50" : "bg-white"}`}>
                  {message.role === "assistant" ? (
                    <div className="shrink-0 h-8 w-8 flex items-center justify-center bg-white border border-slate-100 rounded-full shadow-sm">
                      <img src="/camrail-logo-transparent.png" alt="RailMind" className="h-4 w-auto object-contain" />
                    </div>
                  ) : (
                    <div className="shrink-0 h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-700 font-bold text-xs mt-1">
                      U
                    </div>
                  )}
                  
                  <div className="flex-1 min-w-0 flex flex-col items-start">
                    {/* Main Content */}
                    <div className={`w-full ${message.abstention ? "p-4 bg-red-50 border border-red-100 rounded-xl text-slate-800" : "text-slate-800"}`}>
                      {message.role === "assistant" ? (
                        <div className="relative group max-w-[70ch]">
                          <div className="prose prose-base prose-slate max-w-[70ch] leading-relaxed text-slate-800">
                            {renderFormattedMarkdown(message.content, message.citations)}
                          </div>
                          {/* TTS Button */}
                          <button
                            onClick={() => handleSpeak(message.content)}
                            title={t("assistant.listen")}
                            className="absolute -right-2 top-0 p-1.5 text-slate-500 hover:text-camrail-red hover:bg-slate-100 rounded-lg opacity-0 group-hover:opacity-100 transition-all focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
                          </button>
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap text-base text-slate-800 leading-relaxed font-medium max-w-[70ch]">{message.content}</p>
                      )}
                    </div>

                    {/* Assistant Metadata (Confidence & Citations) */}
                    {message.role === "assistant" && (
                      <div className="w-full mt-4 space-y-3 max-w-[70ch]">
                        {message.confidence && (
                          <div className="flex items-center gap-2">
                            <span
                              title={getConfidenceDescription(message.confidence, language)}
                              className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-md text-xs font-semibold border cursor-help ${confidenceConfig[message.confidence].className}`}
                            >
                              <div className={`h-2 w-2 rounded-full ${message.confidence === 'high' ? 'bg-emerald-500' : message.confidence === 'medium' ? 'bg-amber-500' : 'bg-red-500'}`} />
                              {message.abstention ? "⚠️ " : ""}{confidenceConfig[message.confidence].label}
                              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="opacity-60"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                            </span>
                          </div>
                        )}

                        {/* Insufficient confidence notice & Reformulate button */}
                        {(message.confidence === "insufficient" || message.abstention) && (
                          <div className="mt-3 p-4 bg-amber-50/90 border border-amber-200 rounded-xl text-sm text-amber-950 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-2xs">
                            <div className="flex items-start gap-2.5">
                              <span className="text-amber-600 text-base">⚠️</span>
                              <p className="font-medium leading-relaxed">
                                {t("assistant.insufficient_notice")}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                const lastUser = [...messages.slice(0, index)].reverse().find(m => m.role === "user");
                                if (lastUser) {
                                  setQuestion(lastUser.content);
                                }
                                setTimeout(() => inputRef.current?.focus(), 50);
                              }}
                              className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 cursor-pointer"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-10.05l5.67-5.67"/></svg>
                              <span>{t("assistant.reformulate")}</span>
                            </button>
                          </div>
                        )}

                        {/* Citations Cards */}
                        {message.citations && message.citations.length > 0 && (
                          <div className="mt-4 pt-4 border-t border-slate-100">
                            <p className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-3">
                              {t("assistant.sources_used", { count: message.citations.length })}
                            </p>
                            <div className="grid gap-3 sm:grid-cols-2">
                              {message.citations.map((cit, idx) => {
                                const isVirtual = cit.pagination_type === "virtual";
                                const pagePrefix = isVirtual ? "📄 " : "";
                                const pageBadge = cit.page_start === cit.page_end
                                  ? `${pagePrefix}Page ${cit.page_start}`
                                  : `${pagePrefix}Pages ${cit.page_start}-${cit.page_end}`;
                                const proofText = (cit.evidence && cit.evidence.length > 0 ? cit.evidence[0].text : cit.excerpt) || "";

                                return (
                                  <div 
                                    id={`source-card-${idx + 1}`}
                                    key={idx}
                                    className="group flex flex-col justify-between p-4 rounded-xl border border-slate-200 bg-white hover:border-camrail-red hover:shadow-sm transition-all"
                                  >
                                    <div>
                                      <div className="flex items-center justify-between gap-2 mb-2">
                                        <span className="text-xs font-bold text-camrail-red uppercase tracking-wider">
                                          Source {idx + 1}
                                        </span>
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${isVirtual ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-slate-100 text-slate-700'}`}>
                                          {pageBadge}
                                        </span>
                                      </div>

                                      <h4 className="text-sm font-semibold text-slate-800 line-clamp-1 group-hover:text-camrail-red mb-2 flex items-center gap-2">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-slate-400 group-hover:text-camrail-red transition-colors"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                                        <span className="truncate">{cit.document_title}</span>
                                      </h4>

                                      {proofText && (
                                        <div className="mt-2.5 p-3 rounded-lg bg-slate-50 border-l-4 border-camrail-red border-t border-r border-b border-slate-200 text-sm text-slate-800 font-sans italic leading-relaxed select-text">
                                          &ldquo;{proofText}&rdquo;
                                        </div>
                                      )}
                                    </div>

                                    {cit.document_id && (
                                      <button
                                        type="button"
                                        onClick={() => handleViewInDocument(cit)}
                                        className="mt-3 inline-flex items-center justify-center gap-1.5 w-full py-2 px-3 rounded-lg bg-slate-100 hover:bg-camrail-red hover:text-white text-xs font-semibold text-slate-700 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red cursor-pointer"
                                      >
                                        <span>{t("assistant.view_in_document")}</span>
                                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>
                                      </button>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Indicateur de chargement & étapes : Recherche -> Rédaction avec Skeletons */}
              {loading && (
                <div className="flex flex-col gap-4 p-5 rounded-xl bg-white border border-slate-200 shadow-sm max-w-[70ch]">
                  <div className="flex items-center gap-3">
                    <div className="shrink-0 h-8 w-8 flex items-center justify-center bg-white border border-slate-100 rounded-full shadow-sm">
                      <img src="/camrail-logo-transparent.png" alt="RailMind" className="h-4 w-auto object-contain" />
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1">
                        <span className="h-2 w-2 bg-camrail-red rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                        <span className="h-2 w-2 bg-camrail-red rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                        <span className="h-2 w-2 bg-camrail-red rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                      </div>
                      <span className="text-sm font-semibold text-slate-800">
                        {streamingStatus === "drafting"
                          ? t("assistant.drafting")
                          : t("assistant.searching")}
                      </span>
                    </div>
                  </div>
                  {/* Skeleton des sources en cours d'extraction */}
                  <div className="mt-1 pt-3 border-t border-slate-100 space-y-2">
                    <div className="h-3 w-36 bg-slate-200 rounded animate-pulse"></div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 space-y-2">
                        <div className="flex justify-between items-center">
                          <Skeleton variant="text" className="w-16 h-3" />
                          <Skeleton variant="text" className="w-12 h-3" />
                        </div>
                        <Skeleton variant="text" className="w-4/5 h-4" />
                        <Skeleton variant="rectangular" className="w-full h-10 rounded-lg" />
                      </div>
                      <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 space-y-2 hidden sm:block">
                        <div className="flex justify-between items-center">
                          <Skeleton variant="text" className="w-16 h-3" />
                          <Skeleton variant="text" className="w-12 h-3" />
                        </div>
                        <Skeleton variant="text" className="w-3/4 h-4" />
                        <Skeleton variant="rectangular" className="w-full h-10 rounded-lg" />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {translatingLanguage && (
                <div className="flex items-center justify-center py-4 text-sm text-slate-600 font-medium animate-pulse">
                  {language === 'fr' ? 'Traduction de la conversation...' : 'Translating conversation...'}
                </div>
              )}
              
              <div ref={messagesEndRef} className="h-4" />
            </div>
          )}
        </div>

        {/* Sticky Input Area avec bouton Arrêter */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-slate-50 via-slate-50 to-transparent pt-10 pb-6 px-4">
          <div className="max-w-3xl mx-auto">
            <form 
              onSubmit={handleSubmit}
              className="relative rounded-2xl border border-slate-300 bg-white shadow-lg overflow-hidden focus-within:border-camrail-red focus-within:ring-2 focus-within:ring-camrail-red/20 transition-all"
            >
              <textarea
                ref={inputRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t("chat.placeholder")}
                className="w-full resize-none bg-transparent py-4 pl-4 pr-28 text-base text-slate-900 placeholder-slate-400 focus:outline-none min-h-[60px] max-h-[200px]"
                rows={Math.min(5, Math.max(1, question.split('\n').length))}
                disabled={loading || isListening}
              />
              <div className="absolute right-2 bottom-2 flex items-center gap-1.5">
                {/* Voice Input Button */}
                <button
                  type="button"
                  onClick={toggleListening}
                  title={isListening ? t("chat.stop") : t("chat.listen")}
                  className={`rounded-xl p-2.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-camrail-red ${
                    isListening 
                      ? "text-white bg-red-500 animate-pulse" 
                      : "text-slate-500 hover:text-camrail-red hover:bg-slate-100"
                  }`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
                </button>

                {/* Bouton Arrêter ou Bouton Envoyer */}
                {loading ? (
                  <button
                    type="button"
                    onClick={handleStopGeneration}
                    title={language === 'fr' ? "Arrêter la génération" : "Stop generation"}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs font-semibold shadow-sm transition-all animate-pulse cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-red-600"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect width="18" height="18" x="3" y="3" rx="2"/></svg>
                    <span>{language === 'fr' ? "Arrêter" : "Stop"}</span>
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!question.trim() || isListening}
                    className="rounded-xl p-2.5 text-white bg-camrail-red hover:bg-red-700 disabled:bg-slate-200 disabled:text-slate-400 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-camrail-red"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                  </button>
                )}
              </div>
            </form>
            <p className="text-center text-xs font-medium text-slate-500 mt-3">
              {t("chat.disclaimer")}
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
