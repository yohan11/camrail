import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AssistantPage from "@/app/assistant/page";
import { LanguageProvider } from "@/lib/LanguageContext";
import { getUserFirstName } from "@/lib/auth";
import { SUGGESTED_QUESTIONS } from "@/lib/suggestions";

// Mock AuthGuard to render children directly
vi.mock("@/components/AuthGuard", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// Mock apiFetch
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn().mockImplementation((url: string) => {
    if (url.includes("/documents")) {
      return Promise.resolve({ count: 28, items: [] });
    }
    return Promise.resolve([]);
  }),
}));

// Mock getSession and auth helpers
vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  return {
    ...actual,
    getSession: vi.fn().mockReturnValue({
      email: "jean.dupont@camrail.net",
      role: "admin",
      token: "mock-token",
    }),
  };
});

describe("Assistant Empty State (app/assistant/page.tsx)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (typeof window !== "undefined") {
      window.sessionStorage.clear();
    }
  });

  const renderAssistant = () => {
    return render(
      <LanguageProvider>
        <AssistantPage />
      </LanguageProvider>
    );
  };

  it("extracts and formats first name properly with getUserFirstName", () => {
    expect(getUserFirstName("jean.dupont@camrail.net")).toBe("Jean");
    expect(getUserFirstName("marie-claire.kamga@camrail.net")).toBe("Marie-Claire");
    expect(getUserFirstName("alexandre@camrail.net")).toBe("Alexandre");
    expect(getUserFirstName("")).toBe("");
  });

  it("displays personalized greeting with capitalized first name", async () => {
    renderAssistant();

    await waitFor(() => {
      expect(
        screen.getByText(/bonjour jean/i)
      ).toBeDefined();
    });
  });

  it("displays document count badge", async () => {
    renderAssistant();

    await waitFor(() => {
      expect(
        screen.getByText(/28 documents consultables/i)
      ).toBeDefined();
    });
  });

  it("displays all 4 suggestions from golden_set / suggestions config", async () => {
    renderAssistant();

    await waitFor(() => {
      SUGGESTED_QUESTIONS.forEach((sugg) => {
        const text = sugg.question.fr;
        expect(screen.getByText(text)).toBeDefined();
      });
    });
  });
});
