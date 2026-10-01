import { useNavigate, NavLink } from "react-router-dom";
import { ChevronsUpDown, LogOut, Plus } from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/Logo";
import { IconButton } from "@/components/ui/Button";
import { Menu, type MenuEntry } from "@/components/ui/Menu";
import { CreateWorkspaceDialog } from "@/features/auth/CreateWorkspaceDialog";
import { useSession, useWorkspace } from "@/features/auth/session";
import { useMetrics, useRecovery } from "@/hooks/queries";
import { cn, initials } from "@/utils/format";
import { NAV, type NavItem } from "./nav";

function useBadges() {
  const metrics = useMetrics();
  const recovery = useRecovery();
  const approvals = metrics.data?.awaiting_approval ?? 0;
  const recoveryCount = recovery.data
    ? recovery.data.events.length + recovery.data.outbox.length + recovery.data.actions.length
    : 0;
  return { approvals, recovery: recoveryCount };
}

function NavBadge({ item, counts }: { item: NavItem; counts: { approvals: number; recovery: number } }) {
  if (!item.badge) return null;
  const count = counts[item.badge];
  if (!count) return null;
  return (
    <span className={cn("nav__badge", item.badge === "recovery" && "nav__badge--danger")} aria-label={`${count} need attention`}>
      {count}
    </span>
  );
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, workspaces, signOut, switchWorkspace } = useSession();
  const { workspace, canManage, isDemo } = useWorkspace();
  const counts = useBadges();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);

  const entries: MenuEntry[] = [
    { type: "label", label: "Workspaces" },
    ...workspaces.map<MenuEntry>((w) => ({
      label: w.name,
      description: `${w.role} · ${w.plan}`,
      selected: w.id === workspace.id,
      onSelect: () => {
        switchWorkspace(w.id);
        navigate("/overview");
        onNavigate?.();
      },
    })),
    { type: "separator" },
    { label: "Create workspace", icon: <Plus size={14} />, onSelect: () => setCreating(true) },
  ];

  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="sidebar__brand">
        <Logo />
        <span>Threshold</span>
      </div>

      <nav className="sidebar__nav" aria-label="Main navigation">
        {NAV.map((group) => {
          const items = group.items.filter((i) => (i.visible === "admin" ? canManage : i.visible === "demo" ? isDemo : true));
          if (!items.length) return null;
          return (
            <div className="nav__group" key={group.label ?? "main"}>
              {group.label && <div className="nav__label">{group.label}</div>}
              {items.map((item) => (
                <NavLink key={item.to} to={item.to} className={({ isActive }) => cn("nav__item", isActive && "nav__item--active")} onClick={onNavigate}>
                  <item.icon size={16} aria-hidden />
                  <span>{item.label}</span>
                  <NavBadge item={item} counts={counts} />
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>

      <div className="sidebar__footer">
        <Menu
          label="Switch workspace"
          align="start"
          side="top"
          triggerClassName="ws-switch"
          entries={entries}
          trigger={
            <>
              <span className="ws-switch__avatar" aria-hidden>
                {initials(workspace.name)}
              </span>
              <span className="ws-switch__text">
                <span className="ws-switch__name">{workspace.name}</span>
                <span className="ws-switch__meta">
                  {workspace.role} · {workspace.plan}
                </span>
              </span>
              <ChevronsUpDown size={14} aria-hidden />
            </>
          }
        />
        <div className="user-row">
          <span className="user-row__avatar" aria-hidden>
            {initials(user?.full_name ?? "")}
          </span>
          <span className="user-row__text">
            <span className="user-row__name">{user?.full_name}</span>
            <span className="user-row__email">{user?.email}</span>
          </span>
          <IconButton label="Sign out" onClick={() => signOut()}>
            <LogOut size={15} />
          </IconButton>
        </div>
      </div>
      <CreateWorkspaceDialog open={creating} onClose={() => setCreating(false)} />
    </aside>
  );
}

