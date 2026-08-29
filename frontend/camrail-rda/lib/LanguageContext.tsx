"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export type Language = 'fr' | 'en';

interface LanguageContextProps {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const translations: Record<Language, Record<string, string>> = {
  fr: {
    "login.title": "RailMind Lite",
    "login.subtitle": "Base de Connaissance CAMRAIL",
    "login.email": "Adresse Email",
    "login.password": "Mot de passe",
    "login.button": "Se connecter",
    "login.error": "Erreur de connexion",
    "app.new_chat": "Nouvelle conversation",
    "app.menu": "MENU PRINCIPAL",
    "app.assistant": "Assistant IA",
    "app.documents": "Documents",
    "app.dashboard": "Dashboard",
    "app.history": "HISTORIQUE",
    "app.logout": "Se déconnecter",
    "chat.placeholder": "Posez votre question à RailMind Lite...",
    "chat.disclaimer": "RailMind Lite peut faire des erreurs. Vérifiez toujours les documents sources.",
    "chat.error": "Une erreur est survenue lors de la communication avec l'assistant.",
    "chat.offline": "Mode hors ligne actif. La recherche peut être plus lente.",
    "chat.listen": "Écouter",
    "chat.stop": "Arrêter l'écoute"
  },
  en: {
    "login.title": "RailMind Lite",
    "login.subtitle": "CAMRAIL Knowledge Base",
    "login.email": "Email Address",
    "login.password": "Password",
    "login.button": "Login",
    "login.error": "Login Error",
    "app.new_chat": "New Conversation",
    "app.menu": "MAIN MENU",
    "app.assistant": "AI Assistant",
    "app.documents": "Documents",
    "app.dashboard": "Dashboard",
    "app.history": "HISTORY",
    "app.logout": "Logout",
    "chat.placeholder": "Ask RailMind Lite a question...",
    "chat.disclaimer": "RailMind Lite can make mistakes. Always verify with source documents.",
    "chat.error": "An error occurred while communicating with the assistant.",
    "chat.offline": "Offline mode active. Search may be slower.",
    "chat.listen": "Listen",
    "chat.stop": "Stop listening"
  }
};

const LanguageContext = createContext<LanguageContextProps | undefined>(undefined);

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLanguageState] = useState<Language>('fr');

  useEffect(() => {
    // Check localStorage on mount
    const savedLang = localStorage.getItem('railmind_lang') as Language;
    if (savedLang && (savedLang === 'fr' || savedLang === 'en')) {
      setLanguageState(savedLang);
    }
  }, []);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('railmind_lang', lang);
  };

  const t = (key: string): string => {
    return translations[language][key] || key;
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
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
