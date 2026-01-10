export type LearningConceptsBacklogResponse = Record<string, unknown>;

export type DocumentConceptsBacklogResponse = Record<string, unknown>;

export type LearningConceptsBatchEnqueueRequest = {
  limit?: number;
  topic_id?: number | null;
  min_age_hours?: number;
  force?: boolean;
};

export type DocumentConceptsBatchEnqueueRequest = {
  limit?: number;
  min_age_hours?: number;
  force?: boolean;
};

export type AdminBatchEnqueueResponse = Record<string, unknown>;

