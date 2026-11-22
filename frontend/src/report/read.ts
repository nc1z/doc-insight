export type NotablePoint = { text: string; page: number; quote: string };
export type Entity = { name: string; aliases: string[] };
export type Entities = {
  people: Entity[];
  organisations: Entity[];
  locations: Entity[];
  dates: Entity[];
};
export type Claim = { text: string; document: string; page: number; quote: string };
export type Contradiction = { about: string; claims: Claim[] };

export type DocumentSummaryView = {
  title: string;
  inferredType: string;
  summary: string;
  topics: string[];
  entities: Entities;
  notablePoints: NotablePoint[];
};

export type ReportViewModel = {
  summary: string;
  themes: string[];
  contradictions: Contradiction[];
  entities: Entities;
  takeaways: string[];
  flaggedDocuments: string[];
  excludedFiles: string[];
};

const EMPTY_ENTITIES: Entities = { people: [], organisations: [], locations: [], dates: [] };

function record(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function texts(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map(text).filter((item) => item.length > 0);
}

function entities(value: unknown): Entities {
  const body = record(value);
  if (!body) {
    return EMPTY_ENTITIES;
  }
  const group = (key: string): Entity[] => {
    const items = body[key];
    if (!Array.isArray(items)) {
      return [];
    }
    return items.flatMap((item) => {
      const row = record(item);
      const name = text(row?.name);
      if (!name) {
        return [];
      }
      return [{ name, aliases: texts(row?.aliases) }];
    });
  };
  return {
    people: group('people'),
    organisations: group('organisations'),
    locations: group('locations'),
    dates: group('dates'),
  };
}

function points(value: unknown): NotablePoint[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    const row = record(item);
    const point = text(row?.text);
    const quote = text(row?.quote);
    const page = row?.page;
    if (!point || !quote || typeof page !== 'number') {
      return [];
    }
    return [{ text: point, page, quote }];
  });
}

export function readSummary(value: unknown): DocumentSummaryView | null {
  const body = record(value);
  const summary = text(body?.summary);
  if (!body || !summary) {
    return null;
  }
  return {
    title: text(body.title),
    inferredType: text(body.inferred_type),
    summary,
    topics: texts(body.topics),
    entities: entities(body.entities),
    notablePoints: points(body.notable_points),
  };
}

export function readReport(value: unknown): ReportViewModel | null {
  const body = record(value);
  const summary = text(body?.summary);
  if (!body || !summary) {
    return null;
  }
  const contradictions = Array.isArray(body.contradictions)
    ? body.contradictions.flatMap((item) => {
        const row = record(item);
        const about = text(row?.about);
        const claims = Array.isArray(row?.claims)
          ? row.claims.flatMap((claim) => {
              const side = record(claim);
              const claimText = text(side?.text);
              const document = text(side?.document);
              const quote = text(side?.quote);
              const page = side?.page;
              if (!claimText || !document || !quote || typeof page !== 'number') {
                return [];
              }
              return [{ text: claimText, document, page, quote }];
            })
          : [];
        if (!about || claims.length === 0) {
          return [];
        }
        return [{ about, claims }];
      })
    : [];
  return {
    summary,
    themes: texts(body.themes),
    contradictions,
    entities: entities(body.entities),
    takeaways: texts(body.takeaways),
    flaggedDocuments: texts(body.flagged_documents),
    excludedFiles: texts(body.excluded_files),
  };
}
