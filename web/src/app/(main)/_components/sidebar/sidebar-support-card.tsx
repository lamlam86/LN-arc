import { Radar } from "lucide-react";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function SidebarSupportCard() {
  return (
    <Card
      size="sm"
      className="overflow-hidden border-primary/20 bg-primary/5 shadow-none group-data-[collapsible=icon]:hidden"
    >
      <CardHeader className="min-w-0 px-4">
        <CardTitle className="flex items-center gap-1.5 truncate text-sm">
          <Radar className="size-4 text-primary" />
          Recon Console
        </CardTitle>
        <CardDescription className="line-clamp-3 text-[11px]">
          LN-ARC: Autonomous AI Reconnaissance Console — LLM-driven multi-agent system for network reconnaissance.
        </CardDescription>
      </CardHeader>
    </Card>
  );
}
