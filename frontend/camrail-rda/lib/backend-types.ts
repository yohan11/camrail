export type BackendCitation = {
  document_id?: string;
  document_title: string;
  document_version?: string;
  page_start: number;
  page_end: number;
  section?: string;
  excerpt: string;
};

export type AssistantResponse = {
  request_id?: string;
  query?: string;
  answer: string;
  confidence: "high" | "medium" | "insufficient";
  citations: BackendCitation[];
  duration_ms?: number;
  [key: string]: any;
};

export type DocumentItem = {
  id: string;
  title: string;
  category: string;
  department: string;
  version: string;
  status: string;
  checksum?: string;
  uploaded_by?: string;
  created_at?: string;
};
