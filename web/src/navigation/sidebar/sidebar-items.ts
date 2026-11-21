import {
  Ban,
  Bug,
  FileText,
  FolderOpen,
  LayoutDashboard,
  type LucideIcon,
  MessageSquare,
  Network,
  Radio,
  ScrollText,
  Settings2,
  ShieldAlert,
  Target,
  Terminal,
} from "lucide-react";

export type NavBadge = "new" | "soon";

export interface NavSubItem {
  id: string;
  title: string;
  url: string;
  icon?: LucideIcon;
  badge?: NavBadge;
  disabled?: boolean;
  newTab?: boolean;
}

interface NavItemBase {
  id: string;
  title: string;
  icon?: LucideIcon;
  badge?: NavBadge;
  disabled?: boolean;
  newTab?: boolean;
}

export interface NavMainLinkItem extends NavItemBase {
  url: string;
  subItems?: never;
}

export interface NavMainParentItem extends NavItemBase {
  subItems: NavSubItem[];
}

export type NavMainItem = NavMainLinkItem | NavMainParentItem;

export interface NavGroup {
  id: number;
  label?: string;
  items: NavMainItem[];
}

export const sidebarItems: NavGroup[] = [
  {
    id: 1,
    label: "Features",
    items: [
      { id: "dashboard", title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
      { id: "chat", title: "Chat", url: "/chat", icon: MessageSquare },
      { id: "tasks", title: "Tasks", url: "/function/tasks", icon: Target },
      { id: "findings", title: "Findings", url: "/function/findings", icon: Bug },
      { id: "reports", title: "Reports", url: "/function/tasks/reports", icon: FileText },
      { id: "commands", title: "Tool Runs", url: "/function/commands", icon: Terminal },
      { id: "llm-records", title: "LLM Records", url: "/function/llm-records", icon: Radio },
      { id: "assets", title: "Assets", url: "/function/assets", icon: Network },
      { id: "workspace", title: "Workspace", url: "/function/workspace", icon: FolderOpen },
    ],
  },
  {
    id: 2,
    label: "System",
    items: [
      { id: "intercept", title: "Interception Rules", url: "/system/intercept", icon: ShieldAlert },
      { id: "asset-intercept", title: "Asset Interception", url: "/system/intercept/assets", icon: Ban },
      { id: "logs", title: "Logs", url: "/system/logs", icon: ScrollText },
      { id: "settings", title: "System Settings", url: "/system/settings", icon: Settings2 },
    ],
  },
];
