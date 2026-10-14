import { describe, it, expect } from "vitest";
import {
  formatAuditAction,
  formatConfidence,
  getConfidenceDescription,
  formatDocumentStatus,
  getDocumentStatusDescription,
  AUDIT_ACTION_LABELS,
  CONFIDENCE_LABELS,
  DOCUMENT_STATUS_LABELS,
} from "@/lib/labels";

describe("Dashboard & System Labels (lib/labels.ts)", () => {
  describe("Audit Action Translations", () => {
    it("translates all standard audit actions to clear French", () => {
      expect(formatAuditAction("assistant_query", "fr")).toBe("Question posée");
      expect(formatAuditAction("login_success", "fr")).toBe("Connexion réussie");
      expect(formatAuditAction("login_failed", "fr")).toBe("Échec de connexion");
      expect(formatAuditAction("logout", "fr")).toBe("Déconnexion");
      expect(formatAuditAction("rda_query", "fr")).toBe("Recherche documentaire");
      expect(formatAuditAction("document_upload", "fr")).toBe("Ajout de document");
      expect(formatAuditAction("document_index", "fr")).toBe("Indexation documentaire");
      expect(formatAuditAction("document_activate", "fr")).toBe("Activation de document");
      expect(formatAuditAction("document_archive", "fr")).toBe("Archivage de document");
      expect(formatAuditAction("document_delete", "fr")).toBe("Suppression de document");
    });

    it("does not leave raw English snake_case for known actions", () => {
      Object.keys(AUDIT_ACTION_LABELS).forEach((key) => {
        const frLabel = formatAuditAction(key, "fr");
        expect(frLabel).not.toContain("_");
        expect(frLabel.length).toBeGreaterThan(0);
      });
    });

    it("cleanly formats unlisted custom actions as fallback", () => {
      expect(formatAuditAction("custom_system_check", "fr")).toBe("Custom system check");
      expect(formatAuditAction("", "fr")).toBe("-");
    });
  });

  describe("Confidence Levels and Tooltips", () => {
    it("translates confidence levels correctly to French", () => {
      expect(formatConfidence("high", "fr")).toBe("Élevée");
      expect(formatConfidence("medium", "fr")).toBe("Moyenne");
      expect(formatConfidence("insufficient", "fr")).toBe("Insuffisante");
    });

    it("translates confidence levels correctly to English", () => {
      expect(formatConfidence("high", "en")).toBe("High");
      expect(formatConfidence("medium", "en")).toBe("Medium");
      expect(formatConfidence("insufficient", "en")).toBe("Insufficient");
    });

    it("provides descriptive tooltips for all confidence levels", () => {
      const highDesc = getConfidenceDescription("high", "fr");
      const medDesc = getConfidenceDescription("medium", "fr");
      const lowDesc = getConfidenceDescription("insufficient", "fr");

      expect(highDesc).toContain("Preuves explicites");
      expect(medDesc).toContain("vérification recommandée");
      expect(lowDesc).toContain("inférieur au seuil");
    });
  });

  describe("Document Status Translations", () => {
    it("maps document statuses to clear human-readable labels", () => {
      expect(formatDocumentStatus("active", "fr")).toBe("Prêt");
      expect(formatDocumentStatus("indexed", "fr")).toBe("Prêt");
      expect(formatDocumentStatus("processing", "fr")).toBe("En cours");
      expect(formatDocumentStatus("failed", "fr")).toBe("En erreur");
      expect(formatDocumentStatus("archived", "fr")).toBe("Archivé");
    });

    it("provides explanatory descriptions for document statuses", () => {
      expect(getDocumentStatusDescription("active", "fr")).toContain("disponible");
      expect(getDocumentStatusDescription("processing", "fr")).toContain("en cours");
      expect(getDocumentStatusDescription("failed", "fr")).toContain("erreur");
    });
  });
});
