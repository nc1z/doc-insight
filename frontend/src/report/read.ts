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
export type Section = { heading: string; paragraphs: string[] };

// Both views lead with a one-line headline, then a few one-line points, then sections to read.
export type DocumentSummaryView = {
  title: string;
  inferredType: string;
  headline: string;
  keyPoints: string[];
  sections: Section[];
  topics: string[];
  entities: Entities;
  notablePoints: NotablePoint[];
};

export type ReportViewModel = {
  headline: string;
  keyPoints: string[];
  sections: Section[];
  themes: string[];
  contradictions: Contradiction[];
  entities: Entities;
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

function sections(value: unknown): Section[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    const row = record(item);
    const heading = text(row?.heading);
    const paragraphs = texts(row?.paragraphs);
    return heading && paragraphs.length > 0 ? [{ heading, paragraphs }] : [];
  });
}

// Older results hold one long summary instead of a headline and sections. Split it so they
// still read well: the first sentence becomes the headline and the rest stays as reading.
function fromLongSummary(summary: string): { headline: string; sections: Section[] } {
  const paragraphs = summary
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  const first = paragraphs[0] ?? summary;
  const sentence = /^.*?[.!?](?=\s|$)/.exec(first)?.[0] ?? first;
  const headline = sentence.length > 200 ? `${sentence.slice(0, 197).trimEnd()}…` : sentence;
  return {
    headline,
    sections: summary.length > headline.length ? [{ heading: 'Summary', paragraphs }] : [],
  };
}

export function readSummary(value: unknown): DocumentSummaryView | null {
  const body = record(value);
  const summary = text(body?.summary);
  if (!body || !summary) {
    return null;
  }
  const notablePoints = points(body.notable_points);
  const readSections = sections(body.sections);
  const legacy = readSections.length === 0 ? fromLongSummary(summary) : null;
  const keyPoints = texts(body.key_points);
  return {
    title: text(body.title),
    inferredType: text(body.inferred_type),
    headline: legacy?.headline ?? summary,
    keyPoints:
      keyPoints.length > 0 ? keyPoints : notablePoints.slice(0, 3).map((point) => point.text),
    sections: legacy?.sections ?? readSections,
    topics: texts(body.topics),
    entities: entities(body.entities),
    notablePoints,
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
  const readSections = sections(body.sections);
  const legacy = readSections.length === 0 ? fromLongSummary(summary) : null;
  return {
    headline: legacy?.headline ?? summary,
    keyPoints: texts(body.takeaways),
    sections: legacy?.sections ?? readSections,
    themes: texts(body.themes),
    contradictions,
    entities: entities(body.entities),
    flaggedDocuments: texts(body.flagged_documents),
    excludedFiles: texts(body.excluded_files),
  };
}
