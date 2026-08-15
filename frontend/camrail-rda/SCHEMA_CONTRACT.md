# Frontend-Backend Schema Contract

This document specifies the exact JSON schemas expected by the frontend from the backend API. All responses must conform to these types to ensure correct rendering and user safety.

## Core Types

All core types are defined in `lib/backend-types.ts` and used throughout the frontend. Import from this file to ensure type safety.

### BackendCitation

```typescript
type BackendCitation = {
  document_id?: string;           // Link to /documents/{id}
  document_title: string;         // Required; rendered as link or plain text
  document_version?: string;      // Shown as "v{version}" in UI
  page_start: number;             // Required; start page number
  page_end: number;               // Required; end page number
  section?: string;               // Section/chapter name if applicable
  excerpt: string;                // Required; quoted text from source
};
```

**Frontend Usage:**
- `document_id`: Used to create link to `/documents/${id}` (if present)
- `document_title`: Displayed in citation card header
- `document_version`: Shown in citation metadata (e.g., "v2.1")
- `page_start`, `page_end`: Formatted as "Page X" or "Pages X-Y"
- `section`: Displayed in metadata row if present
- `excerpt`: Quoted as `« {excerpt} »` in citation

**Mapping Example:**
```typescript
{
  "document_id": "sec-policy-2024",
  "document_title": "Security Policy",
  "document_version": "2.1",
  "page_start": 5,
  "page_end": 7,
  "section": "Access Control",
  "excerpt": "All users must use strong passwords of at least 12 characters."
}
```

Renders as:
```
┌─────────────────────────────────────┐
│ Security Policy                     │
│ v2.1 Pages 5-7                      │
│ Section: Access Control             │
│ « All users must use strong         │
│   passwords... »                    │
└─────────────────────────────────────┘
```

### AssistantResponse

```typescript
type AssistantResponse = {
  request_id?: string;                    // Trace ID (optional)
  query?: string;                         // Echo of user query (optional)
  answer: string;                         // Required; the response text
  confidence: "high" | "medium" | "insufficient";  // Required; enum value
  citations: BackendCitation[];           // Array of sources (can be empty)
  duration_ms?: number;                   // Processing time (optional)
  [key: string]: any;                     // Allows forward compatibility
};
```

**Frontend Usage:**
- `answer`: Displayed in chat message bubble
- `confidence`: Maps to UI badge styling and label:
  - `"high"` → green badge "Confiance élevée"
  - `"medium"` → amber badge "Confiance moyenne"
  - `"insufficient"` → **ABSTENTION** (not displayed as normal answer;
    rendered with distinct styling and message "Abstention — Aucune réponse
    sûre disponible")
- `citations`: ALL citations rendered (not just first one)
  - Empty array is acceptable
  - Non-empty array renders under "Sources" heading
  - Each citation rendered as a card with link, version, section, excerpt

**Important:** `confidence: "insufficient"` is NOT a normal low-confidence answer.
It is an **abstention** and must be visually distinguished from confident answers.

### DocumentItem

```typescript
type DocumentItem = {
  id: string;                   // Required; used for `/documents/{id}` link
  title: string;                // Document name
  category: string;             // E.g., "Security", "Operations"
  department: string;           // Owner department
  version: string;              // Version string (e.g., "2.1")
  status: string;               // Enum: "active" | "indexed" | "processing" | "failed"
  checksum?: string;            // Integrity check (optional)
  uploaded_by?: string;         // User who uploaded (optional)
  created_at?: string;          // ISO date string (optional)
};
```

**Frontend Usage:**
- `id`: Links from doclist and citations to `/documents/{id}`
- `title`: Rendered as link in document list
- `version`: Displayed as "v{version}"
- `status`: Rendered as colored badge with status message

## API Endpoints & Contracts

### POST /assistant/query

**Request:**
```json
{
  "query": "What is the company's security policy?"
}
```

**Response (200):**
```json
{
  "request_id": "req-12345",
  "query": "What is the company's security policy?",
  "answer": "The company's security policy requires...",
  "confidence": "high",
  "citations": [
    {
      "document_id": "sec-policy-2024",
      "document_title": "Security Policy",
      "document_version": "2.1",
      "page_start": 1,
      "page_end": 3,
      "section": "Overview",
      "excerpt": "The company's security policy..."
    }
  ],
  "duration_ms": 245
}
```

**Response (401):**
Frontend catches 401, attempts refresh via POST `/auth/refresh`, retries once,
then redirects to `/login` if refresh fails.

**Response (403/5xx):**
Frontend does NOT render as assistant message. Instead displays UI-level error
modal/banner explaining the failure.

### GET /documents

**Response (200):**
```json
[
  {
    "id": "security-policy-v2",
    "title": "Security Policy",
    "category": "Security",
    "department": "Engineering",
    "version": "2.1",
    "status": "active",
    "created_at": "2026-08-01T00:00:00Z"
  },
  ...
]
```

### GET /documents/{id}

**Response (200):**
Document detail page (see `app/documents/[id]/page.tsx` for structure).

### POST /auth/login

**Request:**
```
application/x-www-form-urlencoded
username=user@example.com&password=secret
```

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "role": "user",
  "email": "user@example.com"
}
```

Frontend stores token in memory (via `setAccessToken()`) and persists role/email
to sessionStorage.

### POST /auth/refresh

**Request:**
(Relies on refresh token cookie set by backend)

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "role": "user",
  "email": "user@example.com"
}
```

Frontend updates in-memory token and retries the original request.

## Critical Rules for RDA Compliance

1. **All citations must be rendered** — not just `citations[0]`. Multi-source
   answers must show all sources.

2. **Abstention must be distinct** — `confidence === "insufficient"` must never
   be presented as a confident answer. Use distinct styling and text (yellow
   background, explicit "Abstention" label).

3. **Provenance fields must be preserved** — `document_id`, `document_version`,
   `section` must not be dropped or renamed during transport. These are required
   for audit trail.

4. **Service account must not bypass authorization** — `app/api/ask/route.ts`
   must forward the user's JWT, not use a service account. Backend enforces
   user-level authorization.

5. **Confidence enums must not be translated** — Frontend types must use canonical
   enums (`"high" | "medium" | "insufficient"`). Localization ("élevée", "moyenne",
   "insuffisante") happens only in UI components.

6. **Error status must be propagated** — HTTP errors (401, 403, 500) must be
   handled distinctly by the frontend; do not wrap them in assistant messages.

## Testing

Run schema validation tests:

```bash
cd __tests__
npm test schema-validation.test.ts
```

Or validate types only (no test framework required):

```bash
npx tsc --noEmit
```

## Version History

- **v1.0** (2026-08-11): Initial frontend-backend contract for CAMRAIL RDA.
  - Back-end must return all citations, not filtered on server.
  - Frontend must distinguish abstentions from low-confidence answers.
  - Access token kept in memory, refresh token via secure cookie.
