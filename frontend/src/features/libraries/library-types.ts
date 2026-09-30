export type LibraryKind = "documents" | "evidence";

export interface RequirementLink {
  mapping_id: string;
  id: string;
  external_id: string;
  title: string;
  framework: string;
  framework_version: string;
  rationale: string;
}

export interface ControlLink { mapping_id?: string; id: string; code: string; name: string; }

export interface LibraryRecord {
  id: string;
  name: string;
  description: string;
  document_type?: string;
  version?: string;
  effective_date?: string | null;
  evidence_date?: string | null;
  owner_user_id: string | null;
  owner?: PersonSummary | null;
  notes: string;
  revision: number;
  created_at: string;
  updated_at: string;
  file: {
    id: string;
    original_filename: string;
    extension: string;
    detected_media_type: string;
    byte_size: number;
    sha256: string;
  };
  requirements: RequirementLink[];
  controls: ControlLink[];
}

export interface ControlOption { id: string; code: string; name: string; }
import type { PersonSummary } from "../../app/api/types";
