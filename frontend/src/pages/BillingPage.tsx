import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardSkeleton, DataState } from "@/components/ui/Feedback";
import { Callout, KeyValue, PageHeader, Panel, Time } from "@/components/ui/Layout";
import { useToast } from "@/components/ui/Toast";
import { useWorkspace } from "@/features/auth/session";
import { useBillingPortal, useCheckout } from "@/hooks/mutations";
import { useCommercialStatus, useMembers, usePlans } from "@/hooks/queries";
import type { CommercialStatus, PlanDefinition } from "@/types/api";
import { cn, formatCurrency, formatNumber, humanize } from "@/utils/format";
import type { Tone } from "@/utils/status";

function subscriptionTone(status: string): Tone {
  if (status === "active" || status === "trialing") return "success";
  if (status === "past_due" || status === "unpaid" || status === "incomplete") return "danger";
  if (status === "canceled") return "neutral";
  return "neutral";
}

function Meter({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const tone = limit && pct >= 100 ? "danger" : limit && pct >= 80 ? "warning" : "ok";
  return (
    <div className="meter">
      <div className="meter__head">
        <span>{label}</span>
        <span className="mono small">
          {formatNumber(used)} {limit ? `/ ${formatNumber(limit)}` : <span className="muted">· no limit</span>}
        </span>
      </div>
      {limit ? (
        <div className="meter__track" role="progressbar" aria-valuemin={0} aria-valuemax={limit} aria-valuenow={Math.min(used, limit)} aria-label={`${label} usage`}>
          <div className={cn("meter__fill", `meter__fill--${tone}`)} style={{ width: `${pct}%` }} />
        </div>
      ) : null}
    </div>
  );
}

function limitText(n: number | null): string {
  return n === null ? "Unlimited" : formatNumber(n);
}

function Body({ status, plans, memberCount }: { status: CommercialStatus; plans: Record<string, PlanDefinition>; memberCount: number | null }) {
  const { isOwner } = useWorkspace();
  const checkout = useCheckout();
  const portal = useBillingPortal();
  const limits = status.plan_definition?.limits;
  const redirect = (url: string | null | undefined) => {
    if (url) window.location.assign(url);
  };
  const paid = Object.entries(plans).filter(([key, p]) => key !== status.plan && p.monthly_price_usd !== null);

  return (
    <div className="stack">
      {status.cancel_at_period_end && (
        <Callout tone="warning" title="Subscription ends at the close of this period">
          Access continues until <Time value={status.current_period_end} absolute />.
        </Callout>
      )}
      {!status.billing_configured && (
        <Callout tone="neutral" title="Billing isn't configured on this deployment">
          Checkout and the billing portal are unavailable until Stripe billing is configured.
        </Callout>
      )}

      <div className="split split--even">
        <Panel title="Current plan">
          <div className="plan-head">
            <div>
              <div className="plan-head__name">{status.plan_definition?.name ?? humanize(status.plan)}</div>
              <div className="muted small">
                {status.plan_definition?.monthly_price_usd != null ? `${formatCurrency(status.plan_definition.monthly_price_usd)} per month` : "No monthly price"}
              </div>
            </div>
            <Badge tone={subscriptionTone(status.subscription_status)} dot>{humanize(status.subscription_status)}</Badge>
          </div>
          <KeyValue
            items={[
              { label: "Trial ends", value: status.trial_ends_at ? <Time value={status.trial_ends_at} absolute /> : "—" },
              { label: "Current period ends", value: status.current_period_end ? <Time value={status.current_period_end} absolute /> : "—" },
            ]}
          />
          {isOwner && status.billing_configured && (
            <div className="row plan-actions">
              <Button icon={<ExternalLink size={13} />} loading={portal.isPending} onClick={() => portal.mutate(undefined as never, { onSuccess: (r) => redirect(r.url) })}>
                Manage billing
              </Button>
              <span className="small muted">Payment methods and invoices are handled in the Stripe billing portal.</span>
            </div>
          )}
          {!isOwner && <p className="small muted plan-actions">Only the workspace owner can change the plan or open the billing portal.</p>}
        </Panel>

        <Panel title="Usage" description={`Billing period ${status.usage_period}.`}>
          <div className="stack">
            <Meter label="Workflow executions" used={status.usage.workflow_executions ?? 0} limit={limits?.workflow_executions ?? null} />
            <Meter label="External actions" used={status.usage.external_actions ?? 0} limit={limits?.external_actions ?? null} />
            <Meter label="Team members" used={memberCount ?? 0} limit={limits?.team_members ?? null} />
          </div>
        </Panel>
      </div>

      {paid.length > 0 && (
        <Panel title="Plans" description="Change plan with Stripe Checkout.">
          <div className="plans">
            {paid.map(([key, p]) => (
              <div key={key} className="plan">
                <div className="plan__name">{p.name}</div>
                <div className="plan__price">
                  {formatCurrency(p.monthly_price_usd)} <span className="muted small">/ month</span>
                </div>
                <ul className="plan__list">
                  <li>{limitText(p.limits.workflow_executions)} workflow executions</li>
                  <li>{limitText(p.limits.external_actions)} external actions</li>
                  <li>{limitText(p.limits.team_members)} team members</li>
                  {p.features.map((f) => <li key={f}>{humanize(f)}</li>)}
                </ul>
                <Button variant="primary" disabled={!isOwner || !status.billing_configured} loading={checkout.isPending && checkout.variables === key} onClick={() => checkout.mutate(key, { onSuccess: (r) => redirect(r.checkout_url) })}>
                  Choose {p.name}
                </Button>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

export function BillingPage() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const status = useCommercialStatus();
  const plans = usePlans();
  const members = useMembers();

  useEffect(() => {
    const result = params.get("billing");
    if (!result) return;
    if (result === "success") toast.success("Checkout complete", "Your subscription is being confirmed.");
    else if (result === "cancelled") toast.info("Checkout cancelled", "No changes were made to your plan.");
    setParams({}, { replace: true });
  }, [params, setParams, toast]);

  return (
    <>
      <PageHeader title="Billing" description="Plan, usage and subscription for this workspace." />
      <DataState query={status} errorTitle="Couldn't load billing" loading={<Panel><CardSkeleton lines={5} /></Panel>}>
        {(s) => <Body status={s} plans={plans.data ?? {}} memberCount={members.data?.length ?? null} />}
      </DataState>
    </>
  );
}
