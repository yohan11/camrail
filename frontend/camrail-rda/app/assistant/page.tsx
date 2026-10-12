"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import { apiFetch, ApiError } from "@/lib/api";
import type { BackendCitation, AssistantResponse } from "@/lib/backend-types";
import ReactMarkdown from "react-markdown";
import { useLanguage } from "@/lib/LanguageContext";

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
      label: language === 'fr' ? "Confiance élevée" : "High confidence",
      className: "bg-emerald-100 text-emerald-800 border-emerald-200",
    },
    medium: {
      label: language === 'fr' ? "Confiance moyenne" : "Medium confidence",
      className: "bg-amber-100 text-amber-800 border-amber-200",
    },
    insufficient: {
      label: language === 'fr' ? "Information insuffisante" : "Insufficient information",
      className: "bg-red-100 text-red-800 border-red-200",
    },
  };

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isListening, setIsListening] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

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
          // Small delay before submitting to let state update
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
      // Si on parle déjà, on arrête
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        return;
      }
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = language === 'fr' ? 'fr-FR' : 'en-US';
      window.speechSynthesis.speak(utterance);
    }
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

  // Translate existing messages when language changes
  const [translatingLanguage, setTranslatingLanguage] = useState(false);
  const previousLanguageRef = useRef(language);

  useEffect(() => {
    if (isLoaded && messages.length > 0 && language !== previousLanguageRef.current) {
      previousLanguageRef.current = language;
      
      // We only translate if we have text to translate
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
  }, [language, isLoaded, messages.length]);

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

  async function handleSubmit(e?: any, forcedQuestion?: string) {
    e?.preventDefault();
    const textToSubmit = forcedQuestion || question;
    const trimmedQuestion = textToSubmit.trim();

    if (!trimmedQuestion || loading) return;

    setMessages((current) => [...current, { role: "user", content: trimmedQuestion }]);
    if (!forcedQuestion) setQuestion("");
    setLoading(true);

    try {
      const payload: any = { query: trimmedQuestion, language: language };
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
        const msg = error.body?.detail || error.message || (language === 'fr' ? "Erreur serveur" : "Server error");
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: language === 'fr' 
              ? `Impossible d'effectuer la recherche : ${msg}` 
              : `Unable to perform search: ${msg}`,
            confidence: "insufficient",
            abstention: true,
          },
        ]);
      } else {
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: language === 'fr' 
              ? "Une erreur est survenue lors de la recherche documentaire. Vérifiez que le serveur backend est en cours d'exécution."
              : "An error occurred during document search. Please check that the backend server is running.",
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
              <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">RailMind Lite</h2>
              <p className="text-slate-500 mb-6 text-sm md:text-base font-medium">Votre assistant documentaire CAMRAIL</p>
              
              <p className="text-sm text-slate-600 mb-8 max-w-md">
                Posez une question sur les documents techniques, les procédures ou les règles disponibles.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl w-full">
                {[
                  language === 'fr' ? "En quoi consiste la maintenance préventive selon les procédures ?" : "What does preventive maintenance involve according to the procedures?",
                  language === 'fr' ? "Quel est le rôle principal de la signalisation ferroviaire ?" : "What is the main role of railway signaling?",
                  language === 'fr' ? "À quelle vitesse un train est-il qualifié de grande vitesse ?" : "At what speed is a train classified as high speed?",
                  language === 'fr' ? "Quel est le rôle de l'EPSF en matière de sécurité ?" : "What is the role of the EPSF in terms of safety?"
                ].map((suggestion, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setQuestion(suggestion);
                      setTimeout(() => inputRef.current?.focus(), 10);
                    }}
                    className="group flex items-start gap-3 p-4 border border-slate-200 rounded-xl text-left hover:border-red-200 hover:shadow-md hover:-translate-y-1 transition-all cursor-pointer text-sm text-slate-600 bg-white"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-slate-400 group-hover:text-camrail-red transition-colors mt-0.5"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.9 1.2 1.5 1.5 2.5"></path><path d="M9 18h6"></path><path d="M10 22h4"></path></svg>
                    <span>{suggestion}</span>
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
                        <div className="relative group">
                          <div className="prose prose-sm prose-slate max-w-none leading-relaxed">
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                          </div>
                          {/* TTS Button */}
                          <button
                            onClick={() => handleSpeak(message.content)}
                            title={t("chat.listen")}
                            className="absolute -right-2 top-0 p-1.5 text-slate-400 hover:text-camrail-red hover:bg-slate-100 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
                          </button>
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
                            <span className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-md text-xs font-semibold border ${confidenceConfig[message.confidence].className}`}>
                              <div className={`h-2 w-2 rounded-full ${message.confidence === 'high' ? 'bg-emerald-500' : message.confidence === 'medium' ? 'bg-amber-500' : 'bg-red-500'}`} />
                              {message.abstention ? "⚠ " : ""}{confidenceConfig[message.confidence].label}
                            </span>
                          </div>
                        )}

                        {/* Citations Cards */}
                        {message.citations && message.citations.length > 0 && (
                          <div className="mt-4 pt-4 border-t border-slate-100">
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
                              {language === 'fr' ? `Sources utilisées (${message.citations.length})` : `Sources used (${message.citations.length})`}
                            </p>
                            <div className="grid gap-3 sm:grid-cols-2">
                              {message.citations.map((cit, idx) => {
                                const isVirtual = cit.pagination_type === "virtual";
                                const pagePrefix = isVirtual ? "≈ " : "";
                                const pageBadge = cit.page_start === cit.page_end
                                  ? `${pagePrefix}Page ${cit.page_start}`
                                  : `${pagePrefix}Pages ${cit.page_start}-${cit.page_end}`;
                                const proofText = (cit.evidence && cit.evidence.length > 0 ? cit.evidence[0].text : cit.excerpt) || "";

                                return (
                                  <div 
                                    key={idx}
                                    className="group flex flex-col justify-between p-4 rounded-xl border border-slate-200 bg-white hover:border-camrail-red hover:shadow-sm transition-all"
                                  >
                                    <div>
                                      <div className="flex items-center justify-between gap-2 mb-2">
                                        <span className="text-[11px] font-bold text-camrail-red uppercase tracking-wider">
                                          Source {idx + 1}
                                        </span>
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${isVirtual ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-slate-100 text-slate-700'}`}>
                                          {pageBadge}
                                        </span>
                                      </div>

                                      <h4 className="text-sm font-semibold text-slate-800 line-clamp-1 group-hover:text-camrail-red mb-2 flex items-center gap-2">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-slate-400 group-hover:text-camrail-red transition-colors"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                                        <span className="truncate">{cit.document_title}</span>
                                      </h4>

                                      {/* Preuve complète dans un encadré visible */}
                                      {proofText && (
                                        <div className="mt-2 p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-700 font-mono italic leading-relaxed select-text">
                                          &ldquo;{proofText}&rdquo;
                                        </div>
                                      )}
                                    </div>

                                    {cit.document_id && (
                                      <button
                                        type="button"
                                        onClick={() => handleViewInDocument(cit)}
                                        className="mt-3 inline-flex items-center justify-center gap-1.5 w-full py-1.5 px-3 rounded-lg bg-slate-100 hover:bg-camrail-red hover:text-white text-xs font-semibold text-slate-700 transition-colors"
                                      >
                                        <span>{language === 'fr' ? 'Voir dans le document' : 'View in document'}</span>
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
                      <span className="text-sm text-slate-500 font-medium">
                        {language === 'fr' ? 'Recherche dans les documents...' : 'Searching documents...'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {translatingLanguage && (
                <div className="flex items-center justify-center py-4 text-sm text-slate-400 font-medium animate-pulse">
                  {language === 'fr' ? 'Traduction de la conversation...' : 'Translating conversation...'}
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
                placeholder={t("chat.placeholder")}
                className="w-full resize-none bg-transparent py-4 pl-4 pr-24 text-sm text-slate-900 placeholder-slate-400 focus:outline-none min-h-[60px] max-h-[200px]"
                rows={Math.min(5, Math.max(1, question.split('\n').length))}
                disabled={loading || isListening}
              />
              <div className="absolute right-2 bottom-2 flex items-center gap-1">
                {/* Voice Input Button */}
                <button
                  type="button"
                  onClick={toggleListening}
                  title={isListening ? t("chat.stop") : t("chat.listen")}
                  className={`rounded-xl p-2.5 transition-colors ${
                    isListening 
                      ? "text-white bg-red-500 animate-pulse" 
                      : "text-slate-400 hover:text-camrail-red hover:bg-slate-100"
                  }`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
                </button>
                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={!question.trim() || loading}
                  className="rounded-xl p-2.5 text-white bg-camrail-red hover:bg-camrail-red-dark disabled:bg-slate-200 disabled:text-slate-400 transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
              </div>
            </form>
            <p className="text-center text-xs text-slate-400 mt-3">
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