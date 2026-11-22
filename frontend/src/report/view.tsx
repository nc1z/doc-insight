import { FileText, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';

import type { JobView } from '@/api/client';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { readReport, readSummary, type Entities } from '@/report/read';

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

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</h3>
      {children}
    </section>
  );
}

function Chips({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item) => (
        <li
          key={item}
          className="rounded-full border border-border bg-secondary/60 px-3 py-1 text-sm text-foreground/90"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

function Quote({ children }: { children: ReactNode }) {
  return (
    <blockquote className="border-l-2 border-border pl-3 text-sm leading-6 text-muted-foreground italic">
      {children}
    </blockquote>
  );
}

function Prose({ children }: { children: ReactNode }) {
  return <p className="text-[1.0625rem] leading-7 text-foreground/90">{children}</p>;
}

function EntityList({ entities }: { entities: Entities }) {
  const groups = ENTITY_LABEL.filter((group) => entities[group.key].length > 0);
  if (groups.length === 0) {
    return null;
  }
  return (
    <Section title="Names">
      <div className="grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-2">
        {groups.map((group) => (
          <div key={group.key} className="bg-card p-4">
            <p className="text-xs font-medium text-muted-foreground">{group.label}</p>
            <ul className="mt-2 space-y-1.5">
              {entities[group.key].map((entity) => (
                <li key={entity.name} className="text-sm leading-5">
                  {entity.name}
                  {entity.aliases.length > 0 && (
                    <span className="text-muted-foreground"> · {entity.aliases.join(', ')}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Section>
  );
}

function PlainList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((name) => (
        <li key={name} className="flex items-center gap-2 text-sm">
          <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          <span className="min-w-0 truncate">{name}</span>
        </li>
      ))}
    </ul>
  );
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
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        {job.documents.map((document) => (
          <TabsTrigger key={document.id} value={document.id}>
            <FileText aria-hidden />
            <span className="truncate">{document.filename}</span>
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="overview" className="space-y-9 pt-8">
        <Prose>{report?.summary ?? 'The report is not ready.'}</Prose>
        {report && report.themes.length > 0 && (
          <Section title="Themes">
            <Chips items={report.themes} />
          </Section>
        )}
        {report && report.contradictions.length > 0 && (
          <Section title="Where the documents disagree">
            <div className="space-y-4">
              {report.contradictions.map((item) => (
                <div
                  key={item.about}
                  className="rounded-2xl border border-border bg-card p-5 shadow-card"
                >
                  <p className="flex items-start gap-2 font-medium">
                    <TriangleAlert className="mt-1 size-4 shrink-0 text-warning" aria-hidden />
                    {item.about}
                  </p>
                  <ul className="mt-4 space-y-4 border-t border-border pt-4">
                    {item.claims.map((claim) => (
                      <li
                        key={`${claim.document}:${claim.page}:${claim.quote}`}
                        className="space-y-2"
                      >
                        <p className="text-sm leading-6">{claim.text}</p>
                        <p className="text-xs text-muted-foreground">
                          {claim.document} · p. {claim.page}
                        </p>
                        <Quote>{claim.quote}</Quote>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </Section>
        )}
        {report && <EntityList entities={report.entities} />}
        {report && report.takeaways.length > 0 && (
          <Section title="Takeaways">
            <ol className="space-y-3">
              {report.takeaways.map((item, index) => (
                <li key={item} className="flex gap-3 text-[0.9375rem] leading-6">
                  <span
                    aria-hidden
                    className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-secondary text-[0.6875rem] font-medium text-muted-foreground tabular-nums"
                  >
                    {index + 1}
                  </span>
                  {item}
                </li>
              ))}
            </ol>
          </Section>
        )}
        {flagged.length > 0 && (
          <Section title="Flagged files">
            <PlainList items={flagged} />
          </Section>
        )}
        {excluded.length > 0 && (
          <Section title="Left out">
            <PlainList items={excluded} />
          </Section>
        )}
      </TabsContent>
      {job.documents.map((document) => {
        const summary = readSummary(document.summary);
        return (
          <TabsContent key={document.id} value={document.id} className="space-y-9 pt-8">
            {summary ? (
              <>
                <header>
                  <h2 className="text-xl font-semibold tracking-tight">
                    {summary.title || document.filename}
                  </h2>
                  {summary.inferredType && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {typeLabel(summary.inferredType)}
                    </p>
                  )}
                </header>
                <Prose>{summary.summary}</Prose>
                {summary.topics.length > 0 && (
                  <Section title="Topics">
                    <Chips items={summary.topics} />
                  </Section>
                )}
                {summary.notablePoints.length > 0 && (
                  <Section title="Key details">
                    <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card shadow-card">
                      {summary.notablePoints.map((point) => (
                        <li key={`${point.page}:${point.quote}`} className="space-y-2 p-5">
                          <p className="text-sm leading-6">{point.text}</p>
                          <p className="text-xs text-muted-foreground">p. {point.page}</p>
                          <Quote>{point.quote}</Quote>
                        </li>
                      ))}
                    </ul>
                  </Section>
                )}
                <EntityList entities={summary.entities} />
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
