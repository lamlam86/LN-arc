"use client";

import * as React from "react";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ArrowLeftIcon, DownloadIcon, FileTextIcon, PrinterIcon } from "lucide-react";

import { Markdown } from "@/components/markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { downloadReportMarkdown, fmtReportDate, fmtReportSize } from "@/lib/report-format";
import { reports } from "@/lib/reports-data";

function ReportViewInner() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  const report = reports.find((r) => r.id === id);
  const [lang, setLang] = React.useState<string | null>(null);

  const active = React.useMemo(() => {
    if (!report) return null;
    return report.versions.find((v) => v.lang === (lang ?? report.defaultLang)) ?? report.versions[0];
  }, [report, lang]);

  if (!report || !active) {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-6">
        <h1 className="font-semibold text-xl">Không tìm thấy report</h1>
        <p className="text-muted-foreground text-sm">
          Report <span className="font-mono">{id || "(thiếu id)"}</span> không tồn tại hoặc đã bị xoá.
        </p>
        <Button variant="outline" asChild>
          <Link href="/function/tasks/reports">
            <ArrowLeftIcon /> Danh sách report
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 w-full flex-col">
      <div className="sticky top-0 z-10 border-b bg-background/95 px-4 py-3 backdrop-blur md:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-2">
            <SidebarTrigger className="-ml-1" />
            <div className="min-w-0">
              <h1 className="truncate font-semibold text-xl">{active.title}</h1>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                {report.taskId ? <Badge variant="secondary">Task #{report.taskId}</Badge> : null}
                <Badge variant="outline">{fmtReportSize(new Blob([active.content]).size)}</Badge>
                <span className="text-muted-foreground text-xs">{fmtReportDate(report.created)}</span>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {report.versions.length > 1 ? (
              <div className="flex items-center gap-1">
                {report.versions.map((v) => (
                  <Button
                    key={v.lang}
                    size="sm"
                    variant={active.lang === v.lang ? "default" : "outline"}
                    onClick={() => setLang(v.lang)}
                  >
                    {v.lang.toUpperCase()}
                  </Button>
                ))}
              </div>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadReportMarkdown(`${report.id}.${active.lang}`, active.content)}
            >
              <DownloadIcon /> Tải .md
            </Button>
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <PrinterIcon /> In
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href="/function/tasks/reports">
                <ArrowLeftIcon /> Danh sách
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <div className="w-full p-4 md:p-6">
        <div className="w-full rounded-md border p-4 md:p-6">
          <Markdown text={active.content} />
        </div>
        <p className="mt-3 flex items-center gap-1.5 text-muted-foreground text-xs">
          <FileTextIcon className="size-3.5" /> Report ID: <span className="font-mono">{report.id}</span> ·{" "}
          <span className="font-mono uppercase">{active.lang}</span>
        </p>
      </div>
    </div>
  );
}

// useSearchParams must sit under a Suspense boundary for static export.
export default function ReportViewPage() {
  return (
    <React.Suspense fallback={null}>
      <ReportViewInner />
    </React.Suspense>
  );
}
