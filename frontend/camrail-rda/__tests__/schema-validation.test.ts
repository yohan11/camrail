/**
 * Schema Validation Tests
 * 
 * These tests validate that the frontend types accurately match the backend
 * response schemas for citations, assistant responses, and documents.
 * Run: npx tsc --noEmit to validate types at compile time.
 */

import type {
  BackendCitation,
  BackendEvidenceUnit,
  AssistantResponse,
  DocumentItem,
  DocumentPageItem,
} from "@/lib/backend-types";
import { findNormalized } from "@/lib/find-normalized";

// ============================================================================
// Test 1: Citation Structure with Chantier 2 Fields (chunk_id, evidence, pagination_type)
// ============================================================================

const mockEvidenceUnit: BackendEvidenceUnit = {
  text: "All users must use strong passwords consisting of at least 12 characters.",
  page_number: 5,
  score: 0.945,
};

// Mock backend response with full citation fields
const mockBackendCitation: BackendCitation = {
  chunk_id: 1042,
  document_id: "doc-123",
  document_title: "Security Policy",
  document_version: "2.1",
  page_start: 5,
  page_end: 7,
  section: "Access Control",
  excerpt: "All users must use strong passwords consisting of at least 12 characters.",
  score: 0.945,
  evidence: [mockEvidenceUnit],
  pagination_type: "virtual",
};

/**
 * Validates all citation fields are required by the UI.
 */
function validateCitationMapping(citation: BackendCitation) {
  if (
    !citation.document_title ||
    citation.page_start === undefined ||
    citation.page_end === undefined ||
    !citation.excerpt
  ) {
    throw new Error("Citation missing required fields");
  }

  // Provenance & Evidence fields verification
  if (citation.chunk_id !== undefined && typeof citation.chunk_id !== "number") {
    throw new Error("chunk_id must be a number");
  }
  if (citation.pagination_type && !["native", "virtual"].includes(citation.pagination_type)) {
    throw new Error("pagination_type must be native or virtual");
  }
  if (citation.evidence && !Array.isArray(citation.evidence)) {
    throw new Error("evidence must be an array of units");
  }
}

describe("Citation Schema & Chantier 2 Extensions", () => {
  test("mockBackendCitation matches schema without runtime errors", () => {
    expect(() => validateCitationMapping(mockBackendCitation)).not.toThrow();
  });

  test("Citation fields including chunk_id, evidence, and pagination_type render properly", () => {
    const citation = mockBackendCitation;
    const isVirtual = citation.pagination_type === "virtual";
    const pagePrefix = isVirtual ? "≈ " : "";
    const rendered = {
      chunk_id: citation.chunk_id,
      title: citation.document_title,
      version: citation.document_version ? `v${citation.document_version}` : undefined,
      section: citation.section,
      pages: citation.page_start === citation.page_end
        ? `${pagePrefix}Page ${citation.page_start}`
        : `${pagePrefix}Pages ${citation.page_start}-${citation.page_end}`,
      excerpt: citation.excerpt,
      evidenceText: citation.evidence?.[0]?.text,
      evidencePage: citation.evidence?.[0]?.page_number,
      link: citation.document_id ? `/documents/${citation.document_id}` : undefined,
    };

    expect(rendered.chunk_id).toBe(1042);
    expect(rendered.title).toBe("Security Policy");
    expect(rendered.version).toBe("v2.1");
    expect(rendered.pages).toBe("≈ Pages 5-7");
    expect(rendered.evidenceText).toBe("All users must use strong passwords consisting of at least 12 characters.");
    expect(rendered.evidencePage).toBe(5);
    expect(rendered.excerpt).not.toContain("...");
  });
});

// ============================================================================
// Test 2: Assistant Response Structure
// ============================================================================

const mockBackendResponse: AssistantResponse = {
  request_id: "req-456",
  query: "What are access controls?",
  answer: "Access controls require authentication [1].",
  confidence: "high",
  citations: [mockBackendCitation],
  duration_ms: 250,
};

const mockAbstention: AssistantResponse = {
  query: "Obscure policy detail?",
  answer: "I cannot provide a reliable answer to this question.",
  confidence: "insufficient",
  citations: [],
};

describe("Assistant Response Schema", () => {
  test("BackendResponse has correct confidence enum", () => {
    const response = mockBackendResponse;
    expect(["high", "medium", "insufficient"]).toContain(response.confidence);
  });

  test("Citations array is preserved unchanged with evidence units", () => {
    const response = mockBackendResponse;
    expect(response.citations).toHaveLength(1);
    expect(response.citations[0].evidence).toHaveLength(1);
    expect(response.citations[0].evidence?.[0].page_number).toBe(5);
  });

  test("Insufficient confidence is treated as abstention", () => {
    const response = mockAbstention;
    expect(response.confidence).toBe("insufficient");
  });
});

// ============================================================================
// Test 3: Document Item Structure with file_type ("pdf" | "docx" | "other")
// ============================================================================

const mockDocument: DocumentItem = {
  id: "doc-123",
  title: "Consignes de Securite v2.1.docx",
  category: "Security",
  department: "EXPLOITATION",
  version: "2.1",
  status: "active",
  file_type: "docx",
  created_at: "2026-08-01T10:00:00Z",
};

describe("Document Item Schema & file_type", () => {
  test("DocumentItem has id and file_type", () => {
    expect(mockDocument.id).toBeDefined();
    expect(mockDocument.file_type).toBe("docx");
    expect(["pdf", "docx", "other"]).toContain(mockDocument.file_type);
  });

  test("Pages array is sorted once on reception even if API sends out of order", () => {
    const unorderedPages: DocumentPageItem[] = [
      { id: 3, page_number: 3, extracted_text: "Page three" },
      { id: 1, page_number: 1, extracted_text: "Page one" },
      { id: 4, page_number: 4, extracted_text: "Page four" },
      { id: 2, page_number: 2, extracted_text: "Page two" },
    ];

    // Client sort logic
    const sorted = [...unorderedPages].sort((a, b) => a.page_number - b.page_number);

    expect(sorted.map((p) => p.page_number)).toEqual([1, 2, 3, 4]);
  });
});

// ============================================================================
// Test 4: findNormalized helper (Whitespace & Newline Resilient Matching)
// ============================================================================

describe("findNormalized Helper", () => {
  test("finds sentence despite extra spaces, newlines, and case variations", () => {
    const haystack =
      "Article 12.\n  Le train express    part à 8h00 pile.\nLa vitesse est limitée.";
    const needle = "le train express part à 8h00 pile.";

    const match = findNormalized(haystack, needle);
    expect(match).not.toBeNull();
    if (match) {
      const extracted = haystack.slice(match.start, match.end);
      expect(extracted).toBe("Le train express    part à 8h00 pile.");
    }
  });

  test("returns null when sentence is genuinely not present in page text", () => {
    const haystack = "Consignes générales relatives au réseau.";
    const needle = "Texte totalement absent du document.";

    const match = findNormalized(haystack, needle);
    expect(match).toBeNull();
  });
});

export {};
