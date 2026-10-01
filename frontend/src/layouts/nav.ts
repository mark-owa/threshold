import {
  Activity,
  CheckSquare,
  CreditCard,
  GitBranch,
  LayoutDashboard,
  PlayCircle,
  Plug,
  RotateCcw,
  ScrollText,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  Webhook,
  Zap,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Only shown when the condition holds. */
  visible?: "admin" | "demo";
  badge?: "approvals" | "recovery";
}

export interface NavGroup {
  label: string | null;
  items: NavItem[];
}

/** Only pages backed by real endpoints. */
export const NAV: NavGroup[] = [
  {
    label: null,
    items: [
      { to: "/overview", label: "Overview", icon: LayoutDashboard },
      { to: "/workflows", label: "Workflows", icon: GitBranch },
      { to: "/executions", label: "Executions", icon: Activity },
      { to: "/approvals", label: "Approvals", icon: CheckSquare, badge: "approvals" },
    ],
  },
  {
    label: "Operations",
    items: [
      { to: "/actions", label: "Actions", icon: Zap },
      { to: "/recovery", label: "Recovery", icon: RotateCcw, badge: "recovery" },
      { to: "/audit", label: "Audit log", icon: ScrollText },
    ],
  },
  {
    label: "Platform",
    items: [
      { to: "/integrations", label: "Integrations", icon: Plug },
      { to: "/webhooks", label: "Webhooks", icon: Webhook },
      { to: "/policies", label: "Policies", icon: SlidersHorizontal },
      { to: "/live-execution", label: "Live execution", icon: ShieldCheck, visible: "admin" },
    ],
  },
  {
    label: "Workspace",
    items: [
      { to: "/team", label: "Team", icon: Users },
      { to: "/billing", label: "Billing", icon: CreditCard },
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
  {
    label: "Demo",
    items: [{ to: "/demo", label: "Scenarios", icon: PlayCircle, visible: "demo" }],
  },
];

const TITLES: Record<string, string> = Object.fromEntries(NAV.flatMap((g) => g.items.map((i) => [i.to, i.label])));

/** Breadcrumb trail for the top bar. */
export function crumbsFor(pathname: string): string[] {
  const [, first = "", second] = pathname.split("/");
  const base = TITLES[`/${first}`] ?? "Threshold";
  return second ? [base, "Details"] : [base];
}
