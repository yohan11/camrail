import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { formatConfidence, getConfidenceDescription } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";

interface SourceCardProps {
  sourceNumber: number;
  documentTitle: string;
  pageNumber: number;
  excerpt: string;
  confidence?: "high" | "medium" | "insufficient";
  onView?: () => void;
}

function SourceCard({
  sourceNumber,
  documentTitle,
  pageNumber,
  excerpt,
  confidence = "high",
  onView,
}: SourceCardProps) {
  const confDesc = getConfidenceDescription(confidence, "fr");
  const confLabel = formatConfidence(confidence, "fr");

  return (
    <div
      id={`source-card-${sourceNumber}`}
      className="group flex flex-col justify-between p-4 rounded-xl border border-slate-200 bg-white hover:border-camrail-red transition-all"
    >
      <div>
        <div className="flex items-center justify-between gap-2 mb-2">
          <span className="text-xs font-bold text-camrail-red uppercase tracking-wider">
            Source {sourceNumber}
          </span>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">
              Page {pageNumber}
            </span>
            <Badge
              variant={confidence === "high" ? "success" : confidence === "medium" ? "warning" : "danger"}
              size="sm"
              title={confDesc}
            >
              {confLabel}
            </Badge>
          </div>
        </div>

        <h4 className="text-sm font-semibold text-slate-800 line-clamp-1 mb-2">
          <span className="truncate">{documentTitle}</span>
        </h4>

        {excerpt && (
          <div
            data-testid="citation-quote"
            className="mt-2.5 p-3 rounded-lg bg-slate-50 border-l-4 border-camrail-red border-t border-r border-b border-slate-200 text-sm text-slate-800 font-sans italic leading-relaxed select-text"
          >
            &ldquo;{excerpt}&rdquo;
          </div>
        )}
      </div>

      {onView && (
        <button
          type="button"
          onClick={onView}
          className="mt-3 inline-flex items-center justify-center gap-1.5 w-full py-2 px-3 rounded-lg bg-slate-100 hover:bg-camrail-red hover:text-white text-xs font-semibold text-slate-700 transition-colors"
        >
          Consulter dans le document
        </button>
      )}
    </div>
  );
}

describe("Source Card Component (Assistant)", () => {
  const mockProps: SourceCardProps = {
    sourceNumber: 1,
    documentTitle: "Consignes_Securite_Voie_2024.pdf",
    pageNumber: 12,
    excerpt: "La vitesse maximale autorisée sur les voies de desserte est strictement limitée à 30 km/h.",
    confidence: "high",
  };

  it("renders the document title and page number correctly", () => {
    render(<SourceCard {...mockProps} />);

    expect(screen.getByText("Consignes_Securite_Voie_2024.pdf")).toBeDefined();
    expect(screen.getByText("Page 12")).toBeDefined();
    expect(screen.getByText("Source 1")).toBeDefined();
  });

  it("renders the citation text in standard sans-serif font (NOT font-mono)", () => {
    render(<SourceCard {...mockProps} />);

    const quoteElement = screen.getByTestId("citation-quote");
    expect(quoteElement).toBeDefined();
    expect(quoteElement.textContent).toContain("La vitesse maximale autorisée");

    // Must NOT contain font-mono
    expect(quoteElement.className).not.toContain("font-mono");
    expect(quoteElement.className).toContain("font-sans");
  });

  it("displays confidence badge with translated French label and descriptive threshold tooltip", () => {
    render(<SourceCard {...mockProps} confidence="high" />);

    const badge = screen.getByText("Élevée");
    expect(badge).toBeDefined();

    // Check tooltip on the badge or its container
    const badgeElement = badge.closest("[title]");
    expect(badgeElement).toBeDefined();
    expect(badgeElement?.getAttribute("title")).toContain("Preuves explicites et concordance textuelle forte");
  });

  it("adjusts tooltip and variant for medium and insufficient confidence levels", () => {
    const { unmount } = render(<SourceCard {...mockProps} confidence="medium" />);
    expect(screen.getByText("Moyenne")).toBeDefined();
    expect(screen.getByText("Moyenne").closest("[title]")?.getAttribute("title")).toContain("vérification recommandée");
    unmount();

    render(<SourceCard {...mockProps} confidence="insufficient" />);
    expect(screen.getByText("Insuffisante")).toBeDefined();
    expect(screen.getByText("Insuffisante").closest("[title]")?.getAttribute("title")).toContain("inférieur au seuil");
  });
});
