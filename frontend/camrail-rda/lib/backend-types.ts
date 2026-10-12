export type BackendEvidenceUnit = {
  text: string;
  page_number: number;
  score: number;
};

export type BackendCitation = {
  chunk_id?: number;
  document_id?: string | number;
  document_title: string;
  document_version?: string;
  page_start: number;
  page_end: number;
  section?: string;
  excerpt: string;
  score?: number;
  evidence?: BackendEvidenceUnit[];
  pagination_type?: "native" | "virtual" | string;
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

export type DocumentPageItem = {
  id: string | number;
  page_number: number;
  extracted_text: string;
  extraction_method?: string;
};

export type DocumentItem = {
  id: string | number;
  title: string;
  category: string;
  department: string;
  version: string;
  status: string;
  file_type?: "pdf" | "docx" | "other" | string;
  checksum?: string;
  uploaded_by?: string | number;
  created_at?: string;
  pages?: DocumentPageItem[];
};
