export interface SuggestionItem {
  id: string;
  category: {
    fr: string;
    en: string;
  } | string;
  question: {
    fr: string;
    en: string;
  };
}

export const SUGGESTED_QUESTIONS: SuggestionItem[] = [
  {
    id: "voie_ferree",
    category: {
      fr: "Infrastructure",
      en: "Railway Infrastructure",
    },
    question: {
      fr: "De quoi est composée une voie ferrée classique ?",
      en: "What are the components of a standard railway track?",
    },
  },
  {
    id: "signalisation",
    category: {
      fr: "Signalisation",
      en: "Signaling",
    },
    question: {
      fr: "Quel est le rôle premier de la signalisation ferroviaire ?",
      en: "What is the primary role of railway signaling?",
    },
  },
  {
    id: "stabilite_trains",
    category: {
      fr: "Sécurité & Voie",
      en: "Safety & Track",
    },
    question: {
      fr: "Quels éléments assurent la stabilité des trains sur les rails ?",
      en: "Which components ensure train stability on the rails?",
    },
  },
  {
    id: "grande_vitesse",
    category: {
      fr: "Exploitation",
      en: "Operations",
    },
    question: {
      fr: "À quelle vitesse un train est-il qualifié de grande vitesse ?",
      en: "At what speed is a train classified as high-speed?",
    },
  },
];
