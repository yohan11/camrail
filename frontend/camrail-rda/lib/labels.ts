export type Language = "fr" | "en";

export const CONFIDENCE_LABELS: Record<string, Record<Language, string>> = {
  high: {
    fr: "Élevée",
    en: "High",
  },
  medium: {
    fr: "Moyenne",
    en: "Medium",
  },
  insufficient: {
    fr: "Insuffisante",
    en: "Insufficient",
  },
};

export const CONFIDENCE_DESCRIPTIONS: Record<string, Record<Language, string>> = {
  high: {
    fr: "Preuves explicites et concordance textuelle forte issues des documents internes CAMRAIL.",
    en: "Explicit evidence and strong textual concordance from internal CAMRAIL documents.",
  },
  medium: {
    fr: "Réponse déduite de passages pertinents, vérification recommandée avec les documents originaux.",
    en: "Answer inferred from relevant excerpts, verification recommended with original documents.",
  },
  insufficient: {
    fr: "Sources internes incomplètes ou niveau de certitude inférieur au seuil de fiabilité.",
    en: "Incomplete internal sources or confidence level below the reliability threshold.",
  },
};

export const AUDIT_ACTION_LABELS: Record<string, Record<Language, string>> = {
  assistant_query: {
    fr: "Question posée",
    en: "Question asked",
  },
  login_success: {
    fr: "Connexion réussie",
    en: "Login successful",
  },
  login_failed: {
    fr: "Échec de connexion",
    en: "Login failed",
  },
  logout: {
    fr: "Déconnexion",
    en: "Logout",
  },
  rda_query: {
    fr: "Recherche documentaire",
    en: "Document search",
  },
  document_upload: {
    fr: "Ajout de document",
    en: "Document upload",
  },
  document_index: {
    fr: "Indexation documentaire",
    en: "Document indexing",
  },
  document_activate: {
    fr: "Activation de document",
    en: "Document activation",
  },
  document_archive: {
    fr: "Archivage de document",
    en: "Document archiving",
  },
  document_delete: {
    fr: "Suppression de document",
    en: "Document deletion",
  },
  document_status_change: {
    fr: "Changement de statut",
    en: "Status change",
  },
};

export const DOCUMENT_STATUS_LABELS: Record<string, Record<Language, string>> = {
  active: {
    fr: "Prêt",
    en: "Ready",
  },
  indexed: {
    fr: "Prêt",
    en: "Ready",
  },
  processing: {
    fr: "En cours",
    en: "In progress",
  },
  failed: {
    fr: "En erreur",
    en: "Failed",
  },
  archived: {
    fr: "Archivé",
    en: "Archived",
  },
};

export const DOCUMENT_STATUS_DESCRIPTIONS: Record<string, Record<Language, string>> = {
  active: {
    fr: "Document validé et disponible pour l'interrogation par l'assistant IA.",
    en: "Validated document available for querying by the AI assistant.",
  },
  indexed: {
    fr: "Indexation vectorielle terminée avec succès, document prêt.",
    en: "Vector indexing successfully completed, document ready.",
  },
  processing: {
    fr: "Extraction de texte et découpage en cours dans le moteur local.",
    en: "Text extraction and chunking in progress within local engine.",
  },
  failed: {
    fr: "Une erreur est survenue lors de l'extraction ou de l'indexation.",
    en: "An error occurred during extraction or indexing.",
  },
  archived: {
    fr: "Document archivé et exclu du périmètre de recherche active.",
    en: "Archived document excluded from the active search scope.",
  },
};

/**
 * Traduit une action d'audit avec repli lisible si non répertoriée
 */
export function formatAuditAction(action: string, lang: Language = "fr"): string {
  if (!action) return "-";
  const normalized = action.toLowerCase().trim();
  if (AUDIT_ACTION_LABELS[normalized]) {
    return AUDIT_ACTION_LABELS[normalized][lang];
  }
  // Repli propre : remplacement des underscores et tirets par des espaces, première lettre en majuscule
  const readable = action
    .replace(/[_-]+/g, " ")
    .trim();
  return readable.charAt(0).toUpperCase() + readable.slice(1);
}

/**
 * Traduit un niveau de confiance
 */
export function formatConfidence(level: string, lang: Language = "fr"): string {
  if (!level) return CONFIDENCE_LABELS.insufficient[lang];
  const normalized = level.toLowerCase().trim();
  return CONFIDENCE_LABELS[normalized]?.[lang] || (lang === "fr" ? "Insuffisante" : "Insufficient");
}

/**
 * Renvoie la description/infobulle d'un niveau de confiance
 */
export function getConfidenceDescription(level: string, lang: Language = "fr"): string {
  if (!level) return CONFIDENCE_DESCRIPTIONS.insufficient[lang];
  const normalized = level.toLowerCase().trim();
  return CONFIDENCE_DESCRIPTIONS[normalized]?.[lang] || "";
}

/**
 * Traduit le statut d'un document
 */
export function formatDocumentStatus(status: string, lang: Language = "fr"): string {
  if (!status) return DOCUMENT_STATUS_LABELS.failed[lang];
  const normalized = status.toLowerCase().trim();
  return DOCUMENT_STATUS_LABELS[normalized]?.[lang] || status;
}

/**
 * Renvoie la description d'un statut documentaire
 */
export function getDocumentStatusDescription(status: string, lang: Language = "fr"): string {
  if (!status) return "";
  const normalized = status.toLowerCase().trim();
  return DOCUMENT_STATUS_DESCRIPTIONS[normalized]?.[lang] || "";
}
