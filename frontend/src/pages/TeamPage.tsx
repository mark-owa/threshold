import { useState, type FormEvent } from "react";
import { UserPlus } from "lucide-react";
import { errorMessage } from "@/api/client";
import { RoleBadge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog, Dialog } from "@/components/ui/Dialog";
import { CopyButton } from "@/components/ui/CopyButton";
import { SelectField, TextField } from "@/components/ui/Fields";
import { DataState, EmptyState, TableSkeleton } from "@/components/ui/Feedback";
import { Callout, PageHeader, Panel, Time } from "@/components/ui/Layout";
import { useSession, useWorkspace } from "@/features/auth/session";
import { useInviteMember, useRemoveMember, useRevokeInvitation, useUpdateMemberRole } from "@/hooks/mutations";
import { useInvitations, useMembers } from "@/hooks/queries";
import type { CreatedInvitation, Member, Role } from "@/types/api";
import { initials } from "@/utils/format";
import { ROLE_DESCRIPTION, ROLE_LABEL } from "@/utils/status";

const ROLES: Role[] = ["owner", "admin", "reviewer", "viewer"];
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function InviteDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { role: myRole } = useWorkspace();
  const invite = useInviteMember();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("reviewer");
  const [emailError, setEmailError] = useState<string | undefined>();
  const [created, setCreated] = useState<CreatedInvitation | null>(null);

  const close = () => {
    setEmail("");
    setRole("reviewer");
    setEmailError(undefined);
    setCreated(null);
    invite.reset();
    onClose();
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!EMAIL.test(email.trim())) return setEmailError("Enter a valid email address.");
    setEmailError(undefined);
    invite.mutate({ email: email.trim(), role }, { onSuccess: setCreated });
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title={created ? "Invitation created" : "Invite a teammate"}
      description={created ? undefined : "They'll join this workspace with the role you choose."}
      busy={invite.isPending}
      footer={
        created ? (
          <Button variant="primary" onClick={close}>Done</Button>
        ) : (
          <>
            <Button variant="ghost" onClick={close} disabled={invite.isPending}>Cancel</Button>
            <Button variant="primary" type="submit" form="invite-form" loading={invite.isPending} disabled={!email.trim()}>Create invitation</Button>
          </>
        )
      }
    >
      {created ? (
        <div className="stack">
          <Callout tone="warning" title="Copy this token now">
            It's shown once and Threshold does not email it ({created.delivery}). Share it with {created.email}; they use it on the “Join a team” screen.
          </Callout>
          <div className="token-box">
            <code className="mono">{created.invitation_token}</code>
            <CopyButton value={created.invitation_token} label="Copy invitation token" />
          </div>
          <p className="small muted">Expires <Time value={created.expires_at} absolute />.</p>
        </div>
      ) : (
        <form id="invite-form" className="stack" onSubmit={submit} noValidate>
          <TextField label="Email" type="email" autoFocus value={email} error={emailError} onChange={(e) => setEmail(e.target.value)} />
          <SelectField label="Role" hint={ROLE_DESCRIPTION[role]} value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.filter((r) => r !== "owner" && (r !== "admin" || myRole === "owner")).map((r) => (
              <option key={r} value={r}>{ROLE_LABEL[r]}</option>
            ))}
          </SelectField>
          {invite.isError && <p className="form-error" role="alert">{errorMessage(invite.error)}</p>}
        </form>
      )}
    </Dialog>
  );
}

export function TeamPage() {
  const { user } = useSession();
  const { canManage } = useWorkspace();
  const members = useMembers();
  const invitations = useInvitations(canManage);
  const updateRole = useUpdateMemberRole();
  const remove = useRemoveMember();
  const revoke = useRevokeInvitation();
  const [inviting, setInviting] = useState(false);
  const [removing, setRemoving] = useState<Member | null>(null);

  return (
    <>
      <PageHeader
        title="Team"
        description="Who can access this workspace and what they're allowed to do."
        actions={canManage ? <Button variant="primary" icon={<UserPlus size={14} />} onClick={() => setInviting(true)}>Invite teammate</Button> : undefined}
      />
      <div className="stack">
        <DataState
          query={members}
          errorTitle="Couldn't load members"
          loading={<div className="table-wrap"><TableSkeleton rows={4} columns={4} /></div>}
          isEmpty={(d) => d.length === 0}
          empty={<Panel><EmptyState title="No members" /></Panel>}
        >
          {(rows) => (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th scope="col">Member</th><th scope="col">Email</th><th scope="col">Role</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {rows.map((m) => {
                    const self = m.user_id === user?.user_id;
                    return (
                      <tr key={m.membership_id}>
                        <td>
                          <span className="row">
                            <span className="user-row__avatar" aria-hidden>{initials(m.full_name)}</span>
                            <span className="cell-main">{m.full_name}</span>
                            {self && <span className="small muted">(you)</span>}
                          </span>
                        </td>
                        <td className="muted">{m.email}</td>
                        <td>
                          {canManage && !self ? (
                            <select className="input select select--sm" aria-label={`Role for ${m.full_name}`} value={m.role} disabled={updateRole.isPending} onChange={(e) => updateRole.mutate({ membershipId: m.membership_id, role: e.target.value as Role })}>
                              {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                            </select>
                          ) : (
                            <RoleBadge role={m.role} />
                          )}
                        </td>
                        <td className="cell-actions">
                          {canManage && !self && <Button size="sm" variant="ghost" onClick={() => setRemoving(m)}>Remove</Button>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </DataState>

        {canManage && (
          <Panel title="Invitations" description="Pending and past invitations." flush>
            <DataState query={invitations} errorTitle="Couldn't load invitations" loading={<TableSkeleton rows={2} columns={4} />} compactError isEmpty={(d) => d.length === 0} empty={<EmptyState compact title="No invitations" description="Invite a teammate to give them access." />}>
              {(rows) => (
                <div className="table-wrap">
                  <table className="data">
                    <thead><tr><th scope="col">Email</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Expires</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                    <tbody>
                      {rows.map((i) => (
                        <tr key={i.id}>
                          <td>{i.email}</td>
                          <td><RoleBadge role={i.role} /></td>
                          <td><StatusBadge kind="invitation" value={i.status} /></td>
                          <td><Time value={i.expires_at} /></td>
                          <td className="cell-actions">{i.status === "pending" && <Button size="sm" variant="ghost" loading={revoke.isPending && revoke.variables === i.id} onClick={() => revoke.mutate(i.id)}>Revoke</Button>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </DataState>
          </Panel>
        )}

        <Panel title="Roles" description="What each role can do in this workspace.">
          <dl className="roles">
            {ROLES.map((r) => (
              <div key={r} className="roles__item">
                <dt><RoleBadge role={r} /></dt>
                <dd>{ROLE_DESCRIPTION[r]}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>

      <InviteDialog open={inviting} onClose={() => setInviting(false)} />
      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        tone="danger"
        title={`Remove ${removing?.full_name ?? "member"}?`}
        description="They lose access to this workspace immediately. Their past activity stays in the audit log."
        confirmLabel="Remove member"
        loading={remove.isPending}
        error={remove.isError ? errorMessage(remove.error) : null}
        onConfirm={() => removing && remove.mutate(removing.membership_id, { onSuccess: () => setRemoving(null) })}
      />
    </>
  );
}
