export interface SuggestionItem {
  id: string;
  category: string;
  question: {
    fr: string;
    en: string;
  };
}

export const SUGGESTED_QUESTIONS: SuggestionItem[] = [
  {
    id: "voie_ferree",
    category: "Infrastructure",
    question: {
      fr: "De quoi est composée une voie ferrée classique ?",
      en: "What are the components of a standard railway track?",
    },
  },
  {
    id: "signalisation",
    category: "Signalisation",
    question: {
      fr: "Quel est le rôle premier de la signalisation ferroviaire ?",
      en: "What is the primary role of railway signaling?",
    },
  },
  {
    id: "stabilite_trains",
    category: "Sécurité & Voie",
    question: {
      fr: "Quels éléments assurent la stabilité des trains sur les rails ?",
      en: "Which components ensure train stability on the rails?",
    },
  },
  {
    id: "grande_vitesse",
    category: "Exploitation",
    question: {
      fr: "À quelle vitesse un train est-il qualifié de grande vitesse ?",
      en: "At what speed is a train classified as high-speed?",
    },
  },
];
