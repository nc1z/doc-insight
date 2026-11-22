import { Download, FileText } from 'lucide-react';
import type { ReactNode } from 'react';

import { reportPdfUrl, type JobView } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  readReport,
  readSummary,
  type Contradiction,
  type Entities,
  type PullQuote,
  type Section as ReadingSection,
} from '@/report/read';

const ENTITY_LABEL: { key: keyof Entities; label: string }[] = [
  { key: 'people', label: 'People' },
  { key: 'organisations', label: 'Organisations' },
  { key: 'locations', label: 'Locations' },
  { key: 'dates', label: 'Dates' },
];

function typeLabel(value: string): string {
  if (!value) {
    return '';
  }
  const words = value.replaceAll('_', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

// Each slide is one block with a hairline above it, except the first.
function Slide({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <section className="space-y-5 border-t border-border pt-8 first:border-t-0 first:pt-0">
      {label && (
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {label}
        </h3>
      )}
      {children}
    </section>
  );
}

function Headline({ eyebrow, children }: { eyebrow: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-3 line-clamp-2 text-sm font-medium text-muted-foreground">{eyebrow}</p>
      <h2 className="text-3xl leading-[1.12] font-semibold tracking-[-0.03em] text-balance sm:text-[2.5rem]">
        {children}
      </h2>
    </div>
  );
}

function KeyPoints({ points }: { points: string[] }) {
  if (points.length === 0) {
    return null;
  }
  return (
    <ol className="divide-y divide-border border-t border-border">
      {points.map((point, index) => (
        <li key={point} className="flex items-baseline gap-4 py-3.5">
          <span
            aria-hidden
            className="w-5 shrink-0 font-mono text-xs text-muted-foreground tabular-nums"
          >
            {String(index + 1).padStart(2, '0')}
          </span>
          <p className="text-[1.0625rem] leading-7 text-foreground">{point}</p>
        </li>
      ))}
    </ol>
  );
}

// Quotes sit between paragraphs, spread evenly, so a section reads like an article.
function interleave(section: ReadingSection): ReactNode[] {
  const { paragraphs, quotes } = section;
  const after = new Map<number, PullQuote[]>();
  quotes.forEach((quote, index) => {
    const at = Math.max(0, Math.floor(((index + 1) * paragraphs.length) / (quotes.length + 1)) - 1);
    after.set(at, [...(after.get(at) ?? []), quote]);
  });
  return paragraphs.flatMap((paragraph, index) => [
    <p key={`p:${paragraph}`} className="max-w-[68ch] text-base leading-7 text-foreground/85">
      {paragraph}
    </p>,
    ...(after.get(index) ?? []).map((quote) => (
      <Quote
        key={`q:${quote.page}:${quote.quote}`}
        quote={quote.quote}
        source={quote.document ? `${quote.document} · p. ${quote.page}` : `p. ${quote.page}`}
      />
    )),
  ]);
}

function Reading({ sections }: { sections: ReadingSection[] }) {
  return (
    <div className="space-y-10">
      {sections.map((section) => (
        <article key={section.heading} className="space-y-5">
          <h4 className="text-lg font-semibold tracking-tight">{section.heading}</h4>
          <div className="space-y-5">{interleave(section)}</div>
        </article>
      ))}
    </div>
  );
}

function Quote({ quote, source }: { quote: string; source: string }) {
  return (
    <figure className="ml-1 max-w-[68ch]">
      <blockquote className="border-l-2 border-foreground/15 pl-4 leading-7 text-foreground/75 italic">
        “{quote}”
      </blockquote>
      <figcaption className="mt-1.5 pl-4 text-xs text-muted-foreground">{source}</figcaption>
    </figure>
  );
}

function Disagreements({ items }: { items: Contradiction[] }) {
  return (
    <div className="space-y-9">
      {items.map((item) => (
        <article key={item.about} className="space-y-4">
          <h4 className="text-lg font-semibold tracking-tight">{item.about}</h4>
          {item.claims.map((claim) => (
            <div key={`${claim.document}:${claim.page}:${claim.quote}`} className="space-y-2">
              <p className="text-[0.9375rem] font-medium">{claim.text}</p>
              <Quote quote={claim.quote} source={`${claim.document} · p. ${claim.page}`} />
            </div>
          ))}
        </article>
      ))}
    </div>
  );
}

function Tags({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item) => (
        <li
          key={item}
          className="rounded-full border border-border bg-secondary/60 px-3 py-1 text-sm text-foreground/80"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

function Metadata({ rows }: { rows: { label: string; values: string[] }[] }) {
  const filled = rows.filter((row) => row.values.length > 0);
  if (filled.length === 0) {
    return null;
  }
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6 marker:text-muted-foreground/60">
      {filled.map((row) => (
        <li key={row.label}>
          <span className="text-muted-foreground">{row.label}: </span>
          {row.values.join(', ')}
        </li>
      ))}
    </ul>
  );
}

function entityRows(entities: Entities): { label: string; values: string[] }[] {
  return ENTITY_LABEL.map(({ key, label }) => ({
    label,
    values: entities[key].map((entity) => entity.name),
  }));
}

export function ReportView({ job }: { job: JobView }) {
  const report = readReport(job.report);
  const excluded = [
    ...new Set([
      ...job.excluded_files.map((file) => file.filename),
      ...(report?.excludedFiles ?? []),
    ]),
  ];
  const flagged = [
    ...new Set([
      ...job.documents.filter((document) => document.flagged).map((document) => document.filename),
      ...(report?.flaggedDocuments ?? []),
    ]),
  ];

  return (
    <Tabs defaultValue="overview" className="w-full text-left">
      <div className="mb-3 flex justify-end">
        <Button asChild variant="outline" size="sm">
          <a href={reportPdfUrl(job.id)} download>
            <Download aria-hidden />
            Download PDF
          </a>
        </Button>
      </div>
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        {job.documents.map((document) => (
          <TabsTrigger key={document.id} value={document.id}>
            <FileText aria-hidden />
            <span className="truncate">{document.filename}</span>
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="overview" className="reveal space-y-10 pt-10">
        {report ? (
          <>
            <Slide>
              <Headline eyebrow="Overview">{report.headline}</Headline>
              <KeyPoints points={report.keyPoints.slice(0, 5)} />
            </Slide>
            {(report.sections.length > 0 || report.contradictions.length > 0) && (
              <Slide label="Further reading">
                {report.sections.length > 0 && <Reading sections={report.sections} />}
                {report.contradictions.length > 0 && (
                  <div className="space-y-5">
                    {report.sections.length > 0 && (
                      <h4 className="pt-4 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                        Where the documents disagree
                      </h4>
                    )}
                    <Disagreements items={report.contradictions} />
                  </div>
                )}
              </Slide>
            )}
            {report.themes.length > 0 && (
              <Slide label="Themes">
                <Tags items={report.themes} />
              </Slide>
            )}
            <Slide label="Metadata">
              <Metadata
                rows={[
                  {
                    label: 'Documents',
                    values: job.documents.map((document) => document.filename),
                  },
                  ...entityRows(report.entities),
                  { label: 'Flagged', values: flagged },
                  { label: 'Left out', values: excluded },
                ]}
              />
            </Slide>
          </>
        ) : (
          <p className="text-muted-foreground">The report is not ready.</p>
        )}
      </TabsContent>
      {job.documents.map((document) => {
        const summary = readSummary(document.summary);
        return (
          <TabsContent key={document.id} value={document.id} className="reveal space-y-10 pt-10">
            {summary ? (
              <>
                <Slide>
                  <Headline
                    eyebrow={[summary.title || document.filename, typeLabel(summary.inferredType)]
                      .filter(Boolean)
                      .join(' · ')}
                  >
                    {summary.headline}
                  </Headline>
                  <KeyPoints points={summary.keyPoints.slice(0, 3)} />
                </Slide>
                {summary.sections.length > 0 && (
                  <Slide label="Reading">
                    <Reading sections={summary.sections} />
                  </Slide>
                )}
                {summary.topics.length > 0 && (
                  <Slide label="Topics">
                    <Tags items={summary.topics} />
                  </Slide>
                )}
                <Slide label="Metadata">
                  <Metadata
                    rows={[
                      { label: 'Type', values: [typeLabel(summary.inferredType)].filter(Boolean) },
                      { label: 'File', values: [document.filename] },
                      ...entityRows(summary.entities),
                    ]}
                  />
                </Slide>
              </>
            ) : (
              <p className="text-muted-foreground">This file has no summary yet.</p>
            )}
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
