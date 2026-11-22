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
export type PullQuote = { quote: string; page: number; document: string };
export type Section = { heading: string; paragraphs: string[]; quotes: PullQuote[] };

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

function pullQuotes(value: unknown): PullQuote[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    const row = record(item);
    const quote = text(row?.quote);
    const page = row?.page;
    if (!quote || typeof page !== 'number') {
      return [];
    }
    return [{ quote, page, document: text(row?.document) }];
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
    return heading && paragraphs.length > 0
      ? [{ heading, paragraphs, quotes: pullQuotes(row?.quotes) }]
      : [];
  });
}

const MAX_TAG = 28;

// Cut at the first natural break (comma, colon, semicolon, dash) once there is enough to
// say something; otherwise cut at a word. Only used on results that predate short fields.
function shorten(value: string, max: number): string {
  if (value.length <= max) {
    return value;
  }
  const head = value.slice(0, max + 20);
  const clause = /^(.{30,}?)(?:[,;:]|\s[—–-]\s)\s/.exec(head);
  if (clause && clause[1].length <= max + 20) {
    return `${clause[1].replace(/[.,;:]$/, '')}.`;
  }
  const words = value.slice(0, max - 1).replace(/\s+\S*$/, '');
  return `${words.replace(/[.,;:]$/, '')}…`;
}

// "Channel checks: 15 percent Q3 cut..." becomes "Channel checks".
function tag(value: string): string {
  const label = value.split(':')[0].trim();
  if (label.length <= MAX_TAG) {
    return label;
  }
  const words = label.slice(0, MAX_TAG).replace(/\s+\S*$/, '');
  return words || label.slice(0, MAX_TAG);
}

function tags(value: unknown): string[] {
  return [...new Set(texts(value).map(tag))];
}

const SENTENCE_BREAK = /(?<=[.!?])\s+(?=[A-Z$("'])/;

const LONG_SENTENCE = 220;

// A sentence stitched together with semicolons becomes one sentence per clause.
function splitLong(sentence: string): string[] {
  if (sentence.length <= LONG_SENTENCE) {
    return [sentence];
  }
  const clauses = sentence.split(/;\s+/).map((clause) => clause.trim());
  return clauses.map((clause, index) => {
    const capital = clause.charAt(0).toUpperCase() + clause.slice(1);
    return index < clauses.length - 1 && !/[.!?]$/.test(capital) ? `${capital}.` : capital;
  });
}

// Older results hold one long summary instead of a headline and sections. Break it into
// short paragraphs of two sentences so it reads like an article rather than a wall of text.
function fromLongSummary(summary: string): { headline: string; sections: Section[] } {
  const sentences = summary
    .split(/\n{2,}/)
    .flatMap((part) => part.trim().split(SENTENCE_BREAK))
    .flatMap(splitLong)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  const [first = summary, ...rest] = sentences;
  const paragraphs: string[] = [];
  for (let index = 0; index < rest.length; index += 2) {
    paragraphs.push(rest.slice(index, index + 2).join(' '));
  }
  return {
    headline: shorten(first, 110),
    sections: paragraphs.length > 0 ? [{ heading: 'Summary', paragraphs, quotes: [] }] : [],
  };
}

const MAX_SPREAD = 3;

// Results without pull quotes still have verified notable points. Spread a few of them
// through the reading so quotes sit between paragraphs.
function withQuotes(list: Section[], notable: NotablePoint[]): Section[] {
  if (list.length === 0 || list.some((section) => section.quotes.length > 0)) {
    return list;
  }
  const spread = notable.slice(0, MAX_SPREAD);
  return list.map((section, index) => ({
    ...section,
    quotes: spread
      .filter((_, at) => at % list.length === index)
      .map((point) => ({ quote: point.quote, page: point.page, document: '' })),
  }));
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
      keyPoints.length > 0
        ? keyPoints
        : notablePoints.slice(0, 3).map((point) => shorten(point.text, 110)),
    sections: withQuotes(legacy?.sections ?? readSections, notablePoints),
    topics: tags(body.topics),
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
    keyPoints: texts(body.takeaways).map((point) => (legacy ? shorten(point, 110) : point)),
    sections: legacy?.sections ?? readSections,
    themes: tags(body.themes),
    contradictions,
    entities: entities(body.entities),
    flaggedDocuments: texts(body.flagged_documents),
    excludedFiles: texts(body.excluded_files),
  };
}
