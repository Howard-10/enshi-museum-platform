export interface KnowledgeSeedFile {
  relative_path: string;
  kind: "artifact" | "background";
  artifact?: string | null;
  copied: boolean;
}

export interface KnowledgeSeedResponse {
  seed_name: string;
  description: string;
  total_files: number;
  copied_files: number;
  files: KnowledgeSeedFile[];
}

export interface ArtifactCatalogItem {
  id: string;
  name: string;
  era: string | null;
  location: string | null;
  material: string | null;
  source_rows: number;
  view_count?: number;
}

export interface ArtifactCatalogResponse {
  total: number;
  items: ArtifactCatalogItem[];
}

export interface PopularArtifactItem extends ArtifactCatalogItem {
  view_count: number;
}

export interface PopularArtifactResponse {
  total: number;
  has_visit_data: boolean;
  items: PopularArtifactItem[];
}
