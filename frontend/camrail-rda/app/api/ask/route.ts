import { NextResponse } from "next/server";

type BackendCitation = {
  document_id?: string;
  document_title: string;
  document_version?: string;
  page_start: number;
  page_end: number;
  section?: string;
  excerpt: string;
};

type BackendResponse = {
  request_id?: string;
  query?: string;
  answer: string;
  confidence: "high" | "medium" | "insufficient";
  citations: BackendCitation[];
  duration_ms?: number;
  // allow additional fields
  [key: string]: any;
};

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const question = body.question;

    if (!question || typeof question !== "string") {
      return NextResponse.json(
        {
          error: "Une question est requise.",
        },
        {
          status: 400,
        },
      );
    }

    const backendUrl = process.env.BACKEND_URL;

    if (!backendUrl) {
      throw new Error("BACKEND_URL manquante dans .env.local");
    }

    // Require the caller to provide an Authorization header (user JWT).
    const incomingAuth = request.headers.get("authorization");

    if (!incomingAuth) {
      return NextResponse.json(
        { error: "Authorization header required" },
        { status: 401 },
      );
    }

    const controller = new AbortController();

    const timeout = setTimeout(() => controller.abort(), 30000);

    let assistantResponse: Response;

    try {
      assistantResponse = await fetch(`${backendUrl}/assistant/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: incomingAuth,
        },
        body: JSON.stringify({ query: question }),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }

    if (!assistantResponse.ok) {
      const errorBody = await assistantResponse
        .json()
        .catch(() => ({ status: assistantResponse.status }));

      return NextResponse.json(errorBody, {
        status: assistantResponse.status,
      });
    }

    const backendData: BackendResponse = await assistantResponse.json();

    // Forward backend response unchanged so the frontend receives full
    // provenance (all citations) and canonical confidence enums.
    return NextResponse.json(backendData);
  } catch (error) {
    console.error("ERREUR /api/ask :", error);

    const message =
      error instanceof Error ? error.message : "Erreur inconnue";

    return NextResponse.json({
      answer: `DIAGNOSTIC : ${message}`,
      confidence: "insuffisante",
      source: null,
    });
  }
}