import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/login/page";
import { LanguageProvider } from "@/lib/LanguageContext";

// Mock auth login function
vi.mock("@/lib/auth", () => ({
  login: vi.fn(),
  getSession: vi.fn().mockReturnValue(null),
}));

describe("Login Form Component (app/login/page.tsx)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderLogin = () => {
    return render(
      <LanguageProvider>
        <LoginPage />
      </LanguageProvider>
    );
  };

  it("renders email and password input fields with proper labels and types", () => {
    renderLogin();

    const emailInput = screen.getByLabelText(/adresse email/i) as HTMLInputElement;
    const passwordInput = screen.getByLabelText(/^mot de passe$/i) as HTMLInputElement;

    expect(emailInput).toBeDefined();
    expect(emailInput.type).toBe("email");
    expect(passwordInput).toBeDefined();
    expect(passwordInput.type).toBe("password");
  });

  it("toggles password visibility when clicking the eye icon button", () => {
    renderLogin();

    const passwordInput = screen.getByLabelText(/^mot de passe$/i) as HTMLInputElement;
    expect(passwordInput.type).toBe("password");

    const toggleButton = screen.getByLabelText(/afficher le mot de passe/i);
    expect(toggleButton).toBeDefined();

    // Click to show password
    fireEvent.click(toggleButton);
    expect(passwordInput.type).toBe("text");
    expect(screen.getByLabelText(/masquer le mot de passe/i)).toBeDefined();

    // Click again to hide password
    fireEvent.click(toggleButton);
    expect(passwordInput.type).toBe("password");
    expect(screen.getByLabelText(/afficher le mot de passe/i)).toBeDefined();
  });

  it("disables the submit button when required fields are empty", () => {
    renderLogin();

    const submitBtn = screen.getByRole("button", { name: /se connecter/i }) as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);

    const emailInput = screen.getByLabelText(/adresse email/i);
    const passwordInput = screen.getByLabelText(/^mot de passe$/i);

    fireEvent.change(emailInput, { target: { value: "agent@camrail.net" } });
    expect(submitBtn.disabled).toBe(true);

    fireEvent.change(passwordInput, { target: { value: "secret123" } });
    expect(submitBtn.disabled).toBe(false);
  });

  it("displays friendly French error message when login fails with invalid credentials", async () => {
    const { login } = await import("@/lib/auth");
    (login as any).mockRejectedValueOnce(new Error("Invalid credentials"));

    renderLogin();

    const emailInput = screen.getByLabelText(/adresse email/i);
    const passwordInput = screen.getByLabelText(/^mot de passe$/i);
    const submitBtn = screen.getByRole("button", { name: /se connecter/i });

    fireEvent.change(emailInput, { target: { value: "agent@camrail.net" } });
    fireEvent.change(passwordInput, { target: { value: "wrongpassword" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/identifiant ou mot de passe incorrect/i)
      ).toBeDefined();
    });
  });
});
