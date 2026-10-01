import { useState } from "react";
import { LogOut, Plus } from "lucide-react";
import { RoleBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IdChip } from "@/components/ui/CopyButton";
import { KeyValue, PageHeader, Panel } from "@/components/ui/Layout";
import { CreateWorkspaceDialog } from "@/features/auth/CreateWorkspaceDialog";
import { useSession, useWorkspace } from "@/features/auth/session";
import { humanize } from "@/utils/format";

export function SettingsPage() {
  const { user, signOut } = useSession();
  const { workspace } = useWorkspace();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader title="Settings" description="Workspace details and your account." actions={<Button icon={<Plus size={14} />} onClick={() => setCreating(true)}>New workspace</Button>} />
      <div className="split split--even">
        <Panel title="Workspace" description="Read-only. Plan changes happen under Billing.">
          <KeyValue
            items={[
              { label: "Name", value: workspace.name },
              { label: "Slug", value: <code className="mono">{workspace.slug}</code> },
              { label: "Plan", value: humanize(workspace.plan) },
              { label: "Your role", value: <RoleBadge role={workspace.role} /> },
              { label: "Workspace ID", value: <IdChip id={workspace.id} full /> },
            ]}
          />
        </Panel>
        <Panel title="Account">
          <KeyValue
            items={[
              { label: "Name", value: user?.full_name },
              { label: "Email", value: user?.email },
              { label: "User ID", value: user ? <IdChip id={user.user_id} full /> : "—" },
              { label: "Workspaces", value: user?.memberships.length ?? 0 },
            ]}
          />
          <p className="small muted plan-actions">Your session is kept for this browser tab only and ends when it expires.</p>
          <div className="plan-actions">
            <Button icon={<LogOut size={14} />} onClick={() => signOut()}>Sign out</Button>
          </div>
        </Panel>
      </div>
      <CreateWorkspaceDialog open={creating} onClose={() => setCreating(false)} />
    </>
  );
}
