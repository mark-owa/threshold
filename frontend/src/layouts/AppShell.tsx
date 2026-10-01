import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { LogOut, Menu as MenuIcon, RefreshCw, Settings } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { IconButton } from "@/components/ui/Button";
import { Menu } from "@/components/ui/Menu";
import { CreateWorkspaceDialog } from "@/features/auth/CreateWorkspaceDialog";
import { useSession, useWorkspace } from "@/features/auth/session";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/Feedback";
import { cn, initials } from "@/utils/format";
import { crumbsFor } from "./nav";
import { Sidebar } from "./Sidebar";

function Topbar({ onMenu }: { onMenu: () => void }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, signOut } = useSession();
  const { workspace, orgId, isDemo } = useWorkspace();
  const fetching = useIsFetching({ queryKey: [orgId] }) > 0;
  const crumbs = crumbsFor(pathname);

  return (
    <header className="topbar">
      <IconButton label="Open navigation" className="topbar__menu" onClick={onMenu}>
        <MenuIcon size={18} />
      </IconButton>
      <nav className="crumbs" aria-label="Breadcrumb">
        <span className="crumbs__ws">{workspace.name}</span>
        {crumbs.map((c, i) => (
          <span key={c} className="crumbs__part">
            <span className="crumbs__sep" aria-hidden>
              /
            </span>
            <span className={cn(i === crumbs.length - 1 && "crumbs__current")} aria-current={i === crumbs.length - 1 ? "page" : undefined}>
              {c}
            </span>
          </span>
        ))}
      </nav>
      <div className="topbar__right">
        {isDemo ? <Badge tone="info">Demo workspace</Badge> : <Badge tone="neutral">{workspace.plan}</Badge>}
        <IconButton label={fetching ? "Refreshing data" : "Refresh data"} onClick={() => void queryClient.invalidateQueries({ queryKey: [orgId] })}>
          <RefreshCw size={15} className={cn(fetching && "spin")} />
        </IconButton>
        <Menu
          label="Account menu"
          triggerClassName="avatar-btn"
          trigger={<span aria-hidden>{initials(user?.full_name ?? "")}</span>}
          entries={[
            { type: "label", label: user?.email ?? "" },
            { label: "Settings", icon: <Settings size={14} />, onSelect: () => navigate("/settings") },
            { type: "separator" },
            { label: "Sign out", icon: <LogOut size={14} />, onSelect: () => signOut() },
          ]}
        />
      </div>
    </header>
  );
}

export function AppShell() {
  const { workspace, user, signOut } = useSession();
  const { pathname } = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => setNavOpen(false), [pathname]);
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [pathname]);

  if (!workspace) {
    return (
      <div className="center-screen">
        <EmptyState
          icon={<Logo size={22} />}
          title="Create your first workspace"
          description={`${user?.full_name ?? "You"} aren't a member of any workspace yet. Create one to start, or ask a teammate for an invitation.`}
          action={
            <div className="row">
              <Button variant="primary" onClick={() => setCreating(true)}>
                Create workspace
              </Button>
              <Button variant="ghost" onClick={() => signOut()}>
                Sign out
              </Button>
            </div>
          }
        />
        <CreateWorkspaceDialog open={creating} onClose={() => setCreating(false)} />
      </div>
    );
  }

  return (
    <div className="shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className={cn("shell__sidebar", navOpen && "shell__sidebar--open")}>
        <Sidebar onNavigate={() => setNavOpen(false)} />
      </div>
      {navOpen && <button className="shell__scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
      <div className="shell__main">
        <Topbar onMenu={() => setNavOpen(true)} />
        <main id="main" className="page" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
