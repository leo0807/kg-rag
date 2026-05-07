export interface Section {
  number: string;
  title: string;
  chunk_id: string;
  page_idx?: number | null;
  bbox?: [number, number, number, number] | number[] | null;
}

export interface DocumentDetail {
  doc_id: string;
  title: string;
  version: string;
  issue_date: string;
  sections: Section[];
  refs: string[];
}

export interface SectionContent {
  number: string;
  title: string;
  content: string;
}
