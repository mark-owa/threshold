import { useState, type FormEvent } from "react";
import { Plus, Webhook } from "lucide-react";
import { API_BASE, errorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog, Dialog } from "@/components/ui/Dialog";
import { CopyButton } from "@/components/ui/CopyButton";
import { SecretField, TextField } from "@/components/ui/Fields";
import { DataState, EmptyState, TableSkeleton } from "@/components/ui/Feedback";
import { Callout, PageHeader, Panel, Time } from "@/components/ui/Layout";
import { useWorkspace } from "@/features/auth/session";
import { useCreateWebhook, useDisableWebhook } from "@/hooks/mutations";
import { useWebhookEndpoints } from "@/hooks/queries";
import type { WebhookEndpoint } from "@/types/api";

function CreateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateWebhook();
  const [name, setName] = useState("");
  const [ref, setRef] = useState("");
  const [skew, setSkew] = useState("300");
  const [skewError, setSkewError] = useState<string | undefined>();

  const close = () => {
    setName("");
    setRef("");
    setSkew("300");
    setSkewError(undefined);
    create.reset();
    onClose();
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const n = Number(skew);
    if (!Number.isInteger(n) || n < 30 || n > 3600) {
      setSkewError("Enter a whole number from 30 to 3600.");
      return;
    }
    setSkewError(undefined);
    create.mutate({ name: name.trim(), signing_secret_ref: ref.trim(), allowed_clock_skew_seconds: n }, { onSuccess: close });
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Create webhook endpoint"
      description="Give an external system a signed URL to send events to."
      busy={create.isPending}
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={create.isPending}>Cancel</Button>
          <Button variant="primary" type="submit" form="webhook-form" loading={create.isPending} disabled={name.trim().length < 2 || !ref.trim()}>
            Create endpoint
          </Button>
        </>
      }
    >
      <form id="webhook-form" className="stack" onSubmit={submit} noValidate>
        <TextField label="Name" value={name} maxLength={255} autoFocus placeholder="Support inbox" onChange={(e) => setName(e.target.value)} />
        <SecretField label="Signing secret reference" hint="The name of a secret configured in your deployment, not the secret value." value={ref} onChange={(e) => setRef(e.target.value)} />
        <TextField label="Allowed clock skew (seconds)" type="number" min={30} max={3600} hint="Requests with a timestamp further than this from now are rejected." value={skew} error={skewError} onChange={(e) => setSkew(e.target.value)} />
        {create.isError && <p className="form-error" role="alert">{errorMessage(create.error)}</p>}
      </form>
    </Dialog>
  );
}

export function WebhooksPage() {
  const { canManage } = useWorkspace();
  const query = useWebhookEndpoints();
  const disable = useDisableWebhook();
  const [creating, setCreating] = useState(false);
  const [target, setTarget] = useState<WebhookEndpoint | null>(null);
  const base = API_BASE || window.location.origin;

  return (
    <>
      <PageHeader
        title="Webhooks"
        description="Signed inbound endpoints that turn events from other systems into workflow executions."
        actions={canManage ? <Button variant="primary" icon={<Plus size={14} />} onClick={() => setCreating(true)}>Create endpoint</Button> : undefined}
      />
      <div className="stack">
        <DataState
          query={query}
          errorTitle="Couldn't load webhook endpoints"
          loading={<div className="table-wrap"><TableSkeleton rows={3} columns={6} /></div>}
          isEmpty={(d) => d.length === 0}
          empty={
            <Panel>
              <EmptyState icon={<Webhook size={18} />} title="No webhook endpoints" description="Create an endpoint so another system can send events to Threshold." action={canManage ? <Button variant="primary" onClick={() => setCreating(true)}>Create endpoint</Button> : undefined} />
            </Panel>
          }
        >
          {(rows) => (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Endpoint URL</th>
                    <th scope="col">Signing secret</th>
                    <th scope="col">State</th>
                    <th scope="col" className="num">Clock skew</th>
                    <th scope="col">Created</th>
                    <th scope="col"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((w) => (
                    <tr key={w.id}>
                      <td className="cell-main">{w.name}</td>
                      <td>
                        <span className="idchip">
                          <code className="mono small truncate url-cell" title={`${base}${w.path}`}>{`${base}${w.path}`}</code>
                          <CopyButton value={`${base}${w.path}`} label="Copy endpoint URL" />
                        </span>
                      </td>
                      <td className="muted mono small">Reference: {w.signing_secret_ref}</td>
                      <td>{w.is_active ? <Badge tone="success" dot>Active</Badge> : <Badge dot>Disabled</Badge>}</td>
                      <td className="num">{w.allowed_clock_skew_seconds}s</td>
                      <td><Time value={w.created_at} /></td>
                      <td className="cell-actions">
                        {canManage && w.is_active && <Button size="sm" variant="ghost" onClick={() => setTarget(w)}>Disable</Button>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
        <Callout tone="neutral" title="How senders authenticate">
          Each request must include <code className="mono">X-Threshold-Event-Id</code>, <code className="mono">X-Threshold-Timestamp</code> and <code className="mono">X-Threshold-Signature</code>. The signature is an HMAC-SHA256 of the timestamp, a period, and the raw request body, using the endpoint's signing secret. Requests outside the allowed clock skew are rejected.
        </Callout>
      </div>
      <CreateDialog open={creating} onClose={() => setCreating(false)} />
      <ConfirmDialog
        open={!!target}
        onClose={() => setTarget(null)}
        tone="danger"
        title={`Disable “${target?.name ?? ""}”?`}
        description="The endpoint stops accepting events immediately. Senders will receive an error until you create a new endpoint."
        confirmLabel="Disable endpoint"
        loading={disable.isPending}
        error={disable.isError ? errorMessage(disable.error) : null}
        onConfirm={() => target && disable.mutate(target.id, { onSuccess: () => setTarget(null) })}
      />
    </>
  );
}
