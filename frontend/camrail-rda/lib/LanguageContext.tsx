"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";

export type Language = "fr" | "en";

interface LanguageContextProps {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const translations: Record<Language, Record<string, string>> = {
  fr: {
    // Connexion
    "login.title": "RailMind Lite",
    "login.subtitle": "Base de Connaissance CAMRAIL",
    "login.tagline": "Portail souverain d'intelligence documentaire ferroviaire",
    "login.email": "Adresse Email",
    "login.password": "Mot de passe",
    "login.button": "Se connecter",
    "login.loading": "Connexion en cours...",
    "login.error": "Erreur de connexion. Vérifiez vos identifiants.",
    "login.sso_button": "Se connecter avec Microsoft",
    "login.or_local": "Ou connexion locale (Admin)",
    "login.show_password": "Afficher le mot de passe",
    "login.hide_password": "Masquer le mot de passe",

    // Navigation & Shell
    "app.new_chat": "Nouvelle conversation",
    "app.menu": "MENU PRINCIPAL",
    "app.assistant": "Assistant IA",
    "app.documents": "Documents",
    "app.dashboard": "Tableau de bord",
    "app.history": "HISTORIQUE",
    "app.no_history": "Aucune conversation",
    "app.logout": "Se déconnecter",
    "app.login": "Se connecter",

    // Assistant Chat
    "assistant.greeting_named": "Bonjour {name}, que souhaitez-vous savoir ?",
    "assistant.greeting_default": "Bonjour, que souhaitez-vous savoir ?",
    "assistant.subtitle": "Votre assistant documentaire intelligent pour l'exploitation ferroviaire",
    "assistant.docs_available": "{count} documents consultables",
    "assistant.suggested_title": "Suggestions de questions fréquentes :",
    "assistant.searching": "Recherche dans les documents...",
    "assistant.drafting": "Rédaction de la réponse...",
    "assistant.stop": "Arrêter",
    "assistant.reformulate": "Reformuler",
    "assistant.insufficient_notice": "Je n'ai pas trouvé de réponse fiable dans les documents. Essayez de reformuler ou de préciser le sujet.",
    "assistant.sources_used": "Sources utilisées ({count})",
    "assistant.view_in_document": "Voir dans le document",
    "assistant.listen": "Écouter la réponse",
    "assistant.stop_listening": "Arrêter l'écoute",
    "chat.placeholder": "Posez votre question sur les procédures et documents CAMRAIL...",
    "chat.disclaimer": "RailMind Lite peut faire des erreurs. Vérifiez toujours les documents sources.",
    "chat.error": "Une erreur est survenue lors de la communication avec l'assistant.",
    "chat.offline": "Mode local actif. Traitement sécurisé hors ligne.",

    // Documents
    "docs.title": "Gestion Documentaire",
    "docs.subtitle": "Référentiel des procédures, fiches de sécurité et notices techniques ferroviaires.",
    "docs.new_button": "Nouveau document",
    "docs.search_placeholder": "Rechercher par titre de document...",
    "docs.status_ready": "Prêts",
    "docs.status_processing": "En cours",
    "docs.status_failed": "En erreur",
    "docs.status_archived": "Archivés",
    "docs.filter_all": "Tous les statuts",
    "docs.filter_category": "Toutes catégories",
    "docs.filter_department": "Tous départements",
    "docs.stuck_warning": "Ce document est en cours de traitement depuis plus de 10 minutes.",
    "docs.retry_index": "Relancer l'indexation",
    "docs.empty_title": "Aucun document trouvé",
    "docs.empty_desc": "Aucun document ne correspond à vos critères de recherche actuels.",
    "docs.reset_filters": "Réinitialiser les filtres",
    "docs.upload_modal_title": "Importer un document",
    "docs.upload_drag_title": "Glissez-déposez votre document ici",
    "docs.upload_drag_sub": "ou cliquez pour sélectionner un fichier depuis votre poste",
    "docs.upload_format_hint": "Formats acceptés : PDF, DOCX (taille max 50 Mo)",
    "docs.upload_progress": "Envoi et analyse documentaire en cours...",
    "docs.upload_success": "Document importé avec succès dans le système.",

    // Tableau de bord
    "dashboard.title": "Tableau de Bord",
    "dashboard.subtitle": "Aperçu global de l'activité de l'assistant IA et du système de gestion documentaire.",
    "dashboard.queries_today": "Requêtes (Aujourd'hui)",
    "dashboard.queries_total": "Sur un total historique de {count}",
    "dashboard.confidence_score": "Score de confiance global",
    "dashboard.reliable_rate": "{rate}% de réponses à confiance élevée ou moyenne",
    "dashboard.recent_queries": "Requêtes Récentes",
    "dashboard.audit_events": "Événements d'Audit (24h)",
    "dashboard.no_chart_data": "Données historiques insuffisantes pour afficher le graphique.",
  },
  en: {
    // Login
    "login.title": "RailMind Lite",
    "login.subtitle": "CAMRAIL Knowledge Base",
    "login.tagline": "Sovereign Railway Document Intelligence Portal",
    "login.email": "Email Address",
    "login.password": "Password",
    "login.button": "Sign In",
    "login.loading": "Signing in...",
    "login.error": "Login error. Please check your credentials.",
    "login.sso_button": "Sign in with Microsoft",
    "login.or_local": "Or local login (Admin)",
    "login.show_password": "Show password",
    "login.hide_password": "Hide password",

    // Navigation & Shell
    "app.new_chat": "New Conversation",
    "app.menu": "MAIN MENU",
    "app.assistant": "AI Assistant",
    "app.documents": "Documents",
    "app.dashboard": "Dashboard",
    "app.history": "HISTORY",
    "app.no_history": "No conversations",
    "app.logout": "Logout",
    "app.login": "Sign in",

    // Assistant Chat
    "assistant.greeting_named": "Hello {name}, how can I assist you today?",
    "assistant.greeting_default": "Hello, how can I assist you today?",
    "assistant.subtitle": "Your intelligent document assistant for railway operations",
    "assistant.docs_available": "{count} searchable documents",
    "assistant.suggested_title": "Suggested frequently asked questions:",
    "assistant.searching": "Searching documents...",
    "assistant.drafting": "Drafting response...",
    "assistant.stop": "Stop",
    "assistant.reformulate": "Rephrase",
    "assistant.insufficient_notice": "I could not find a reliable answer in the documents. Try rephrasing or clarifying the topic.",
    "assistant.sources_used": "Sources used ({count})",
    "assistant.view_in_document": "View in document",
    "assistant.listen": "Listen to response",
    "assistant.stop_listening": "Stop listening",
    "chat.placeholder": "Ask your question regarding CAMRAIL procedures and rules...",
    "chat.disclaimer": "RailMind Lite can make mistakes. Always verify with source documents.",
    "chat.error": "An error occurred while communicating with the assistant.",
    "chat.offline": "Local mode active. Secure offline processing.",

    // Documents
    "docs.title": "Document Management",
    "docs.subtitle": "Repository of procedures, safety sheets, and railway technical notices.",
    "docs.new_button": "New Document",
    "docs.search_placeholder": "Search by document title...",
    "docs.status_ready": "Ready",
    "docs.status_processing": "Processing",
    "docs.status_failed": "Failed",
    "docs.status_archived": "Archived",
    "docs.filter_all": "All statuses",
    "docs.filter_category": "All categories",
    "docs.filter_department": "All departments",
    "docs.stuck_warning": "This document has been processing for more than 10 minutes.",
    "docs.retry_index": "Retry Indexing",
    "docs.empty_title": "No documents found",
    "docs.empty_desc": "No documents matched your current search filters.",
    "docs.reset_filters": "Reset filters",
    "docs.upload_modal_title": "Upload Document",
    "docs.upload_drag_title": "Drag & drop your document here",
    "docs.upload_drag_sub": "or click to select a file from your computer",
    "docs.upload_format_hint": "Accepted formats: PDF, DOCX (max size 50 MB)",
    "docs.upload_progress": "Uploading and analyzing document...",
    "docs.upload_success": "Document successfully uploaded to system.",

    // Dashboard
    "dashboard.title": "Dashboard",
    "dashboard.subtitle": "Comprehensive overview of AI assistant activity and document management.",
    "dashboard.queries_today": "Queries (Today)",
    "dashboard.queries_total": "Out of a total history of {count}",
    "dashboard.confidence_score": "Overall confidence score",
    "dashboard.reliable_rate": "{rate}% high or medium confidence responses",
    "dashboard.recent_queries": "Recent Queries",
    "dashboard.audit_events": "Audit Events (24h)",
    "dashboard.no_chart_data": "Insufficient historical data to render chart.",
  },
};

const LanguageContext = createContext<LanguageContextProps | undefined>(undefined);

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLanguageState] = useState<Language>("fr");

  useEffect(() => {
    const savedLang = localStorage.getItem("railmind_lang") as Language;
    if (savedLang && (savedLang === "fr" || savedLang === "en")) {
      setLanguageState(savedLang);
    }
  }, []);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem("railmind_lang", lang);
  };

  const t = (key: string, params?: Record<string, string | number>): string => {
    let str = translations[language]?.[key] || translations.fr[key] || key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        str = str.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
      });
    }
    return str;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = (): LanguageContextProps => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
};
