"use client";

import * as React from "react";

import { DownloadIcon, FileTextIcon, SearchIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { downloadReportMarkdown, fmtReportDate, fmtReportSize } from "@/lib/report-format";
import { reports } from "@/lib/reports-data";

function reportHref(id: string): string {
  return `/function/tasks/reports/view/?id=${encodeURIComponent(id)}`;
}

export default function ReportsPage() {
  const [query, setQuery] = React.useState("");

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return reports;
    return reports.filter((r) => `${r.title} ${r.taskId} ${r.summary}`.toLowerCase().includes(q));
  }, [query]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h1 className="flex items-center gap-2 font-semibold text-xl">
          <FileTextIcon className="size-5" /> Reports
        </h1>
        <div className="relative w-full md:w-72">
          <SearchIcon className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm theo task, tiêu đề…"
            className="pl-8"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground text-sm">Chưa có report.</CardContent>
        </Card>
      ) : null}

      {filtered.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((r) => (
            <Card key={r.id} className="flex flex-col">
              <CardHeader className="gap-2">
                <CardTitle className="text-base leading-snug">
                  <a
                    href={reportHref(r.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="hover:text-primary hover:underline"
                  >
                    {r.title}
                  </a>
                </CardTitle>
                <CardDescription className="flex flex-wrap items-center gap-1.5">
                  {r.taskId ? <Badge variant="secondary">Task #{r.taskId}</Badge> : null}
                  {r.versions.map((v) => (
                    <Badge key={v.lang} variant="secondary" className="uppercase">
                      {v.lang}
                    </Badge>
                  ))}
                  <Badge variant="outline">{fmtReportSize(r.size)}</Badge>
                  <span className="text-xs">{fmtReportDate(r.created)}</span>
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-2">
                  <Button size="sm" asChild>
                    <a href={reportHref(r.id)} target="_blank" rel="noreferrer">
                      <FileTextIcon className="size-4" /> Mở tab mới
                    </a>
                  </Button>
                  {r.versions.map((v) => (
                    <Button
                      key={v.lang}
                      size="sm"
                      variant="outline"
                      onClick={() => downloadReportMarkdown(`${r.id}.${v.lang}`, v.content)}
                    >
                      <DownloadIcon className="size-4" />{" "}
                      {r.versions.length > 1 ? `Tải ${v.lang.toUpperCase()}` : "Tải .md"}
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  );
}
