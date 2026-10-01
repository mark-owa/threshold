import { useState, type FormEvent, type ReactNode } from "react";
import { errorMessage, API_BASE } from "@/api/client";
import { commercialApi } from "@/api/commercial";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { CheckboxField, SecretField, TextField } from "@/components/ui/Fields";
import { Callout, KeyValue } from "@/components/ui/Layout";
import { useToast } from "@/components/ui/Toast";
import { useWorkspace } from "@/features/auth/session";
import { useSaveGenericRest, useSaveShopify, useSaveStripe, useSyncShopifyOrder } from "@/hooks/mutations";
import { useCommercialStatus } from "@/hooks/queries";
import type { Integration, ShopifyOrderSync } from "@/types/api";
import { formatCurrency } from "@/utils/format";

type Errors = Record<string, string | undefined>;

function cfgString(i: Integration | undefined, key: string, fallback = ""): string {
  const v = i?.config?.[key];
  return typeof v === "string" ? v : typeof v === "number" ? String(v) : fallback;
}
function cfgBool(i: Integration | undefined, key: string, fallback: boolean): boolean {
  const v = i?.config?.[key];
  return typeof v === "boolean" ? v : fallback;
}

function intInRange(raw: string, min: number, max: number, label: string): string | undefined {
  const n = Number(raw);
  if (!Number.isInteger(n) || n < min || n > max) return `${label} must be a whole number from ${min} to ${max}.`;
  return undefined;
}

function FormFrame({ id, onSubmit, error, children, footer }: { id: string; onSubmit: (e: FormEvent) => void; error: string | null; children: ReactNode; footer: ReactNode }) {
  return (
    <form id={id} className="stack" onSubmit={onSubmit} noValidate>
      {children}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="row">{footer}</div>
    </form>
  );
}

const SECRET_NOTE = "This is the name of a secret configured in your deployment, not the secret value. Stored references are never shown again.";

// ── Shopify ─────────────────────────────────────────────────────────────────
export function ShopifyForm({ integration, onSaved }: { integration?: Integration; onSaved: () => void }) {
  const { orgId, canManage, canReview } = useWorkspace();
  const toast = useToast();
  const save = useSaveShopify();
  const sync = useSyncShopifyOrder();
  const commercial = useCommercialStatus();
  const [f, setF] = useState({
    shop_domain: cfgString(integration, "shop_domain"),
    credential_ref: "",
    webhook_secret_ref: "",
    api_version: cfgString(integration, "api_version", "2026-07"),
    timeout_seconds: cfgString(integration, "timeout_seconds", "10"),
    refund_enabled: cfgBool(integration, "refund_enabled", false),
    is_enabled: integration?.is_enabled ?? true,
  });
  const [errors, setErrors] = useState<Errors>({});
  const [webhookPath, setWebhookPath] = useState<string | null>(null);
  const [order, setOrder] = useState("");
  const [synced, setSynced] = useState<ShopifyOrderSync | null>(null);
  const [installShop, setInstallShop] = useState("");
  const [installing, setInstalling] = useState(false);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const errs: Errors = {};
    if (f.shop_domain.trim().length < 8) errs.shop_domain = "Enter the shop domain, e.g. your-store.myshopify.com.";
    if (!f.credential_ref.trim()) errs.credential_ref = "Enter the credential reference.";
    if (f.api_version.trim().length < 7) errs.api_version = "Enter an API version such as 2026-07.";
    errs.timeout_seconds = intInRange(f.timeout_seconds, 1, 60, "Timeout");
    setErrors(errs);
    if (Object.values(errs).some(Boolean)) return;
    save.mutate(
      {
        shop_domain: f.shop_domain.trim(),
        credential_ref: f.credential_ref.trim(),
        webhook_secret_ref: f.webhook_secret_ref.trim() || null,
        api_version: f.api_version.trim(),
        timeout_seconds: Number(f.timeout_seconds),
        refund_enabled: f.refund_enabled,
        is_enabled: f.is_enabled,
      },
      {
        onSuccess: (r) => {
          setWebhookPath(r.webhook_path ?? null);
          setF((p) => ({ ...p, credential_ref: "", webhook_secret_ref: "" }));
          if (!r.webhook_path) onSaved();
        },
      },
    );
  };

  const install = async () => {
    setInstalling(true);
    try {
      const res = await commercialApi.shopifyInstall(orgId, installShop.trim());
      if (res.authorization_url) window.location.assign(res.authorization_url);
      else toast.error("Couldn't start the Shopify install", "The API did not return an authorization URL.");
    } catch (err) {
      toast.error("Couldn't start the Shopify install", errorMessage(err));
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div className="stack">
      {!canManage && <Callout tone="neutral">Admin access is required to change integrations. You can still test order sync below.</Callout>}
      <FormFrame
        id="shopify-form"
        onSubmit={submit}
        error={save.isError ? errorMessage(save.error) : null}
        footer={
          <Button variant="primary" type="submit" loading={save.isPending} disabled={!canManage}>
            Save Shopify settings
          </Button>
        }
      >
        <fieldset className="fieldset" disabled={!canManage || save.isPending}>
          <TextField label="Shop domain" hint="Must end in .myshopify.com and be on this deployment's allowed hosts." value={f.shop_domain} error={errors.shop_domain} placeholder="your-store.myshopify.com" onChange={(e) => set("shop_domain", e.target.value)} />
          <SecretField label="Admin API credential reference" hint={SECRET_NOTE} placeholder={integration?.credential_configured ? "Stored — enter a reference to replace it" : "SHOPIFY_ADMIN_TOKEN"} value={f.credential_ref} error={errors.credential_ref} onChange={(e) => set("credential_ref", e.target.value)} />
          <SecretField label="Webhook secret reference" optional hint="Used to verify webhooks Shopify sends to Threshold." value={f.webhook_secret_ref} onChange={(e) => set("webhook_secret_ref", e.target.value)} />
          <div className="form-grid">
            <TextField label="API version" className="mono" value={f.api_version} error={errors.api_version} onChange={(e) => set("api_version", e.target.value)} />
            <TextField label="Timeout (seconds)" type="number" min={1} max={60} value={f.timeout_seconds} error={errors.timeout_seconds} onChange={(e) => set("timeout_seconds", e.target.value)} />
          </div>
          <CheckboxField label="Use Shopify to execute refunds" hint="When off, Threshold can read orders but won't issue refunds through Shopify." checked={f.refund_enabled} onChange={(e) => set("refund_enabled", e.target.checked)} />
          <CheckboxField label="Integration enabled" checked={f.is_enabled} onChange={(e) => set("is_enabled", e.target.checked)} />
        </fieldset>
      </FormFrame>

      {webhookPath && (
        <Callout tone="success" title="Saved. Point your Shopify webhooks here." actions={<CopyButton value={`${API_BASE || window.location.origin}${webhookPath}`} label="Copy webhook URL" />}>
          <code className="mono">{`${API_BASE || window.location.origin}${webhookPath}`}</code>
        </Callout>
      )}

      {commercial.data?.shopify_oauth_configured && canManage && (
        <section className="stack stack--sm">
          <h3 className="section-label">Install with Shopify OAuth</h3>
          <div className="row">
            <input className="input grow" aria-label="Shop domain for OAuth install" placeholder="your-store.myshopify.com" value={installShop} onChange={(e) => setInstallShop(e.target.value)} />
            <Button loading={installing} disabled={installShop.trim().length < 8} onClick={() => void install()}>
              Install
            </Button>
          </div>
        </section>
      )}

      {integration && canReview && (
        <section className="stack stack--sm">
          <h3 className="section-label">Test the connection</h3>
          <p className="small muted">Fetch an order from Shopify to confirm credentials work. Nothing is changed in Shopify.</p>
          <div className="row">
            <input className="input grow mono" aria-label="Order number to sync" placeholder="Order number, e.g. 1001" value={order} onChange={(e) => setOrder(e.target.value)} />
            <Button loading={sync.isPending} disabled={!order.trim()} onClick={() => sync.mutate(order.trim(), { onSuccess: setSynced })}>
              Sync order
            </Button>
          </div>
          {sync.isError && (
            <p className="form-error" role="alert">
              {errorMessage(sync.error)}
            </p>
          )}
          {synced && (
            <KeyValue
              items={[
                { label: "Order", value: synced.order_number },
                { label: "Total", value: formatCurrency(synced.total, synced.currency) },
                { label: "Refunded", value: formatCurrency(synced.refunded, synced.currency) },
                { label: "Refundable", value: formatCurrency(synced.refundable, synced.currency) },
              ]}
            />
          )}
        </section>
      )}
    </div>
  );
}

// ── Stripe ──────────────────────────────────────────────────────────────────
export function StripeForm({ integration, onSaved }: { integration?: Integration; onSaved: () => void }) {
  const { canManage } = useWorkspace();
  const save = useSaveStripe();
  const [f, setF] = useState({
    credential_ref: "",
    api_version: cfgString(integration, "api_version"),
    timeout_seconds: cfgString(integration, "timeout_seconds", "10"),
    refund_enabled: cfgBool(integration, "refund_enabled", true),
    is_enabled: integration?.is_enabled ?? true,
  });
  const [errors, setErrors] = useState<Errors>({});
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const errs: Errors = {};
    if (!f.credential_ref.trim()) errs.credential_ref = "Enter the credential reference.";
    errs.timeout_seconds = intInRange(f.timeout_seconds, 1, 60, "Timeout");
    setErrors(errs);
    if (Object.values(errs).some(Boolean)) return;
    save.mutate(
      { credential_ref: f.credential_ref.trim(), api_version: f.api_version.trim() || null, timeout_seconds: Number(f.timeout_seconds), refund_enabled: f.refund_enabled, is_enabled: f.is_enabled },
      { onSuccess: () => { setF((p) => ({ ...p, credential_ref: "" })); onSaved(); } },
    );
  };

  return (
    <div className="stack">
      {!canManage && <Callout tone="neutral">Admin access is required to change integrations.</Callout>}
      <FormFrame id="stripe-form" onSubmit={submit} error={save.isError ? errorMessage(save.error) : null} footer={<Button variant="primary" type="submit" loading={save.isPending} disabled={!canManage}>Save Stripe settings</Button>}>
        <fieldset className="fieldset" disabled={!canManage || save.isPending}>
          <SecretField label="Secret key reference" hint={SECRET_NOTE} placeholder={integration?.credential_configured ? "Stored — enter a reference to replace it" : "STRIPE_SECRET_KEY"} value={f.credential_ref} error={errors.credential_ref} onChange={(e) => set("credential_ref", e.target.value)} />
          <div className="form-grid">
            <TextField label="API version" optional className="mono" value={f.api_version} onChange={(e) => set("api_version", e.target.value)} />
            <TextField label="Timeout (seconds)" type="number" min={1} max={60} value={f.timeout_seconds} error={errors.timeout_seconds} onChange={(e) => set("timeout_seconds", e.target.value)} />
          </div>
          <CheckboxField label="Use Stripe to execute refunds" checked={f.refund_enabled} onChange={(e) => set("refund_enabled", e.target.checked)} />
          <CheckboxField label="Integration enabled" checked={f.is_enabled} onChange={(e) => set("is_enabled", e.target.checked)} />
        </fieldset>
      </FormFrame>
    </div>
  );
}

// ── Generic REST ────────────────────────────────────────────────────────────
export function RestForm({ integration, onSaved }: { integration?: Integration; onSaved: () => void }) {
  const { canManage } = useWorkspace();
  const save = useSaveGenericRest();
  const [f, setF] = useState({
    base_url: cfgString(integration, "base_url"),
    refund_path: cfgString(integration, "refund_path", "/refunds"),
    verify_path_template: cfgString(integration, "verify_path_template", "/refunds/{provider_operation_id}"),
    reconcile_path_template: cfgString(integration, "reconcile_path_template", "/refunds/{provider_operation_id}"),
    credential_ref: "",
    timeout_seconds: cfgString(integration, "timeout_seconds", "10"),
    failure_threshold: cfgString(integration, "failure_threshold", "3"),
    recovery_timeout_seconds: cfgString(integration, "recovery_timeout_seconds", "30"),
    is_enabled: integration?.is_enabled ?? true,
  });
  const [errors, setErrors] = useState<Errors>({});
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const errs: Errors = {};
    if (!/^https?:\/\/.{3,}/.test(f.base_url.trim())) errs.base_url = "Enter a full URL starting with https://.";
    if (!f.refund_path.trim()) errs.refund_path = "Enter the refund path.";
    errs.timeout_seconds = intInRange(f.timeout_seconds, 1, 60, "Timeout");
    errs.failure_threshold = intInRange(f.failure_threshold, 1, 20, "Failure threshold");
    errs.recovery_timeout_seconds = intInRange(f.recovery_timeout_seconds, 5, 3600, "Recovery timeout");
    setErrors(errs);
    if (Object.values(errs).some(Boolean)) return;
    save.mutate(
      {
        base_url: f.base_url.trim(),
        refund_path: f.refund_path.trim(),
        verify_path_template: f.verify_path_template.trim(),
        reconcile_path_template: f.reconcile_path_template.trim(),
        credential_ref: f.credential_ref.trim() || null,
        timeout_seconds: Number(f.timeout_seconds),
        failure_threshold: Number(f.failure_threshold),
        recovery_timeout_seconds: Number(f.recovery_timeout_seconds),
        is_enabled: f.is_enabled,
      },
      { onSuccess: () => { setF((p) => ({ ...p, credential_ref: "" })); onSaved(); } },
    );
  };

  return (
    <div className="stack">
      {!canManage && <Callout tone="neutral">Admin access is required to change integrations.</Callout>}
      <FormFrame id="rest-form" onSubmit={submit} error={save.isError ? errorMessage(save.error) : null} footer={<Button variant="primary" type="submit" loading={save.isPending} disabled={!canManage}>Save REST settings</Button>}>
        <fieldset className="fieldset" disabled={!canManage || save.isPending}>
          <TextField label="Base URL" className="mono" placeholder="https://api.example.com" hint="The host must be on this deployment's allowed list." value={f.base_url} error={errors.base_url} onChange={(e) => set("base_url", e.target.value)} />
          <div className="form-grid">
            <TextField label="Refund path" className="mono" value={f.refund_path} error={errors.refund_path} onChange={(e) => set("refund_path", e.target.value)} />
            <SecretField label="Credential reference" optional hint={integration?.credential_configured ? "A reference is stored. Leaving this empty saves without one." : SECRET_NOTE} value={f.credential_ref} onChange={(e) => set("credential_ref", e.target.value)} />
            <TextField label="Verify path template" className="mono" value={f.verify_path_template} onChange={(e) => set("verify_path_template", e.target.value)} />
            <TextField label="Reconcile path template" className="mono" value={f.reconcile_path_template} onChange={(e) => set("reconcile_path_template", e.target.value)} />
          </div>
          <div className="form-grid">
            <TextField label="Timeout (seconds)" type="number" min={1} max={60} value={f.timeout_seconds} error={errors.timeout_seconds} onChange={(e) => set("timeout_seconds", e.target.value)} />
            <TextField label="Failures before circuit opens" type="number" min={1} max={20} value={f.failure_threshold} error={errors.failure_threshold} onChange={(e) => set("failure_threshold", e.target.value)} />
            <TextField label="Recovery timeout (seconds)" type="number" min={5} max={3600} value={f.recovery_timeout_seconds} error={errors.recovery_timeout_seconds} onChange={(e) => set("recovery_timeout_seconds", e.target.value)} />
          </div>
          <CheckboxField label="Integration enabled" checked={f.is_enabled} onChange={(e) => set("is_enabled", e.target.checked)} />
        </fieldset>
      </FormFrame>
    </div>
  );
}
