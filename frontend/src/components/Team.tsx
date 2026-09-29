import React, { useState } from "react";
import { Empty } from "./common";
import type { Invitation, Member } from "../types";

interface TeamProps {
  members: Member[];
  invitations: Invitation[];
  currentUserId: string | undefined;
  canManage: boolean;
  latestInviteToken: string;
  onInvite: (email: string, role: string) => void;
  onRoleChange: (membershipId: string, role: string) => void;
  onRemove: (membershipId: string) => void;
  onRevoke: (invitationId: string) => void;
}

export function Team({ members, invitations, currentUserId, canManage, latestInviteToken, onInvite, onRoleChange, onRemove, onRevoke }: TeamProps) {
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("reviewer");
  return <>
    <section className="panel"><div className="panel-head"><div><h2>Invite a reviewer or administrator</h2><p>Invitations expire after seven days. Until email delivery is connected, Threshold exposes the raw token exactly once for manual delivery.</p></div></div>
      {canManage ? <div className="team-invite-form"><input type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="reviewer@company.com" /><select value={inviteRole} onChange={e => setInviteRole(e.target.value)}><option value="reviewer">Reviewer</option><option value="viewer">Viewer</option><option value="admin">Admin</option></select><button className="primary" onClick={() => onInvite(inviteEmail, inviteRole)}>Create invite</button></div> : <p className="permission-note">Only owners and admins can create invitations.</p>}
      {latestInviteToken && <div className="invite-token"><span>ONE-TIME INVITATION TOKEN</span><code>{latestInviteToken}</code><small>Send this securely to the invited teammate. Threshold stores only its hash.</small></div>}
    </section>
    <section className="panel"><div className="panel-head"><div><h2>Workspace members</h2><p>Roles are tenant-scoped. At least one owner must remain at all times.</p></div><span className="count">{members.length}</span></div>
      {members.length === 0 ? <Empty text="No members loaded." /> : members.map((member) => <div className="member-row" key={member.membership_id}><div><strong>{member.full_name}{member.user_id === currentUserId ? " · you" : ""}</strong><span>{member.email}</span></div>{canManage ? <div className="member-actions"><select value={member.role} onChange={e => onRoleChange(member.membership_id, e.target.value)}><option value="owner">Owner</option><option value="admin">Admin</option><option value="reviewer">Reviewer</option><option value="viewer">Viewer</option></select><button className="outline danger-outline" disabled={member.user_id === currentUserId} onClick={() => onRemove(member.membership_id)}>Remove</button></div> : <span className="badge neutral">{member.role}</span>}</div>)}
    </section>
    {canManage && <section className="panel"><div className="panel-head"><div><h2>Invitations</h2><p>Pending, accepted, expired, and revoked invitation records remain visible for operations review.</p></div></div>{invitations.length === 0 ? <Empty text="No invitation history yet." /> : invitations.map((invite) => <div className="member-row" key={invite.id}><div><strong>{invite.email}</strong><span>{invite.role} · expires {new Date(invite.expires_at).toLocaleString()}</span></div><div className="member-actions"><span className={`badge ${invite.status === "pending" ? "medium" : "neutral"}`}>{invite.status}</span>{invite.status === "pending" && <button className="outline danger-outline" onClick={() => onRevoke(invite.id)}>Revoke</button>}</div></div>)}</section>}
  </>;
}
