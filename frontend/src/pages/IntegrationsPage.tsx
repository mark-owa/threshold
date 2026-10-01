import { useState } from "react";
import { Cog, CreditCard, Globe, Plug, ShoppingBag } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { CardSkeleton, DataState } from "@/components/ui/Feedback";
import { Callout, KeyValue, PageHeader, Panel } from "@/components/ui/Layout";
import { useWorkspace } from "@/features/auth/session";
import { RestForm, ShopifyForm, StripeForm } from "@/features/integrations/IntegrationForms";
import { useIntegrations } from "@/hooks/queries";
import type { Integration, IntegrationProvider } from "@/types/api";
import { humanize } from "@/utils/format";
import type { Tone } from "@/utils/status";

interface Catalog {
  provider: IntegrationProvider;
  name: string;
  description: string;
  icon: typeof Plug;
}

const CONFIGURABLE: Catalog[] = [
  { provider: "shopify", name: "Shopify", description: "Read orders and issue refunds through the Shopify Admin API.", icon: ShoppingBag },
  { provider: "stripe", name: "Stripe", description: "Execute refunds against Stripe payments.", icon: CreditCard },
  { provider: "generic_rest", name: "Generic REST API", description: "Send refund requests to any HTTPS API, with verification and reconciliation paths.", icon: Globe },
];

interface State {
  label: string;
  tone: Tone;
  detail: string;
}

function stateOf(i: Integration | undefined): State {
  if (!i) return { label: "Not connected", tone: "neutral", detail: "Not configured in this workspace." };
  if (!i.is_enabled) return { label: "Disabled", tone: "neutral", detail: "Configured but turned off." };
  if (i.health === "circuit_open") return { label: "Needs attention", tone: "danger", detail: `Circuit open after ${i.consecutive_failures} consecutive failures. Calls are paused until it recovers.` };
  if (!i.credential_configured) return { label: "Needs attention", tone: "warning", detail: "No credential reference is stored." };
  if (i.consecutive_failures > 0) return { label: "Degraded", tone: "warning", detail: `${i.consecutive_failures} of ${i.failure_threshold} failures before the circuit opens.` };
  return { label: "Connected", tone: "success", detail: "Healthy. No recent failures." };
}

function Card({ item, integration, onConfigure, canConfigure, blockedReason }: { item: Catalog; integration?: Integration; onConfigure: () => void; canConfigure: boolean; blockedReason: string | null }) {
  const state = stateOf(integration);
  const Icon = item.icon;
  const refunds = integration?.config?.refund_enabled;
  return (
    <article className="integration">
      <header className="integration__head">
        <span className="integration__icon">
          <Icon size={18} aria-hidden />
        </span>
        <div className="grow">
          <h3 className="integration__name">{item.name}</h3>
          <p className="integration__desc">{item.description}</p>
        </div>
        <Badge tone={state.tone} dot>
          {state.label}
        </Badge>
      </header>
      <p className="integration__state">{state.detail}</p>
      {integration && (
        <KeyValue
          items={[
            { label: "Credential", value: integration.credential_configured ? "Reference stored" : "Not set" },
            ...(typeof refunds === "boolean" ? [{ label: "Executes refunds", value: refunds ? "Yes" : "No" }] : []),
            { label: "Failure threshold", value: `${integration.consecutive_failures} / ${integration.failure_threshold}` },
          ]}
        />
      )}
      <footer className="integration__foot">
        <Button size="sm" variant={integration ? "secondary" : "primary"} onClick={onConfigure} disabled={!canConfigure}>
          {integration ? "Configure" : "Connect"}
        </Button>
        {blockedReason && <span className="small muted">{blockedReason}</span>}
      </footer>
    </article>
  );
}

export function IntegrationsPage() {
  const { isDemo } = useWorkspace();
  const query = useIntegrations();
  const [editing, setEditing] = useState<Catalog | null>(null);

  return (
    <>
      <PageHeader title="Integrations" description="Services Threshold can act on. Credentials are stored as references to your deployment's secrets and are never displayed after saving." />
      {isDemo && (
        <div className="section">
          <Callout tone="info" title="Demo workspace">
            Live integrations can't be connected in a demo workspace. Demo scenarios run against built-in mock providers.
          </Callout>
        </div>
      )}
      <DataState
        query={query}
        errorTitle="Couldn't load integrations"
        loading={
          <div className="integrations">
            {[0, 1, 2].map((i) => (
              <Panel key={i}>
                <CardSkeleton lines={4} />
              </Panel>
            ))}
          </div>
        }
      >
        {(integrations) => {
          const byProvider = new Map(integrations.map((i) => [i.provider, i]));
          const mocks = integrations.filter((i) => i.provider.startsWith("mock_"));
          return (
            <div className="stack">
              <div className="integrations">
                {CONFIGURABLE.map((item) => (
                  <Card key={item.provider} item={item} integration={byProvider.get(item.provider)} canConfigure={!isDemo} blockedReason={isDemo ? "Unavailable in demo workspaces" : null} onConfigure={() => setEditing(item)} />
                ))}
              </div>
              {mocks.length > 0 && (
                <Panel title="Built-in demo providers" description="Simulated services used for demos and tests. They never contact a real system." flush>
                  <ul className="list">
                    {mocks.map((m) => {
                      const state = stateOf(m);
                      return (
                        <li key={m.id} className="list__item list__item--static">
                          <Cog size={16} className="list__icon" aria-hidden />
                          <span className="list__text">
                            <span className="list__title">{humanize(m.provider)}</span>
                            <span className="list__sub">{state.detail}</span>
                          </span>
                          <Badge tone={state.tone} dot>
                            {state.label}
                          </Badge>
                        </li>
                      );
                    })}
                  </ul>
                </Panel>
              )}
            </div>
          );
        }}
      </DataState>

      <Dialog variant="drawer" open={!!editing} onClose={() => setEditing(null)} title={editing ? `${editing.name} settings` : ""} description="Changes apply to new actions immediately.">
        {editing && query.data && (
          <>
            {editing.provider === "shopify" && <ShopifyForm integration={query.data.find((i) => i.provider === "shopify")} onSaved={() => setEditing(null)} />}
            {editing.provider === "stripe" && <StripeForm integration={query.data.find((i) => i.provider === "stripe")} onSaved={() => setEditing(null)} />}
            {editing.provider === "generic_rest" && <RestForm integration={query.data.find((i) => i.provider === "generic_rest")} onSaved={() => setEditing(null)} />}
          </>
        )}
      </Dialog>
    </>
  );
}
