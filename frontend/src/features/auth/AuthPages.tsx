import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { SecretField, TextField } from "@/components/ui/Fields";
import { Callout } from "@/components/ui/Layout";
import { AuthLayout } from "@/layouts/AuthLayout";
import { slugify } from "@/utils/format";
import { useSession } from "./session";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

type Errors = Record<string, string | undefined>;

function useAuthForm() {
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setFormError(null);
    try {
      await action();
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return { busy, formError, run };
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="form-error" role="alert">
      {message}
    </p>
  );
}

/** Redirects signed-in users away from the auth screens. */
function useRedirectTarget() {
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  return from && from !== "/login" ? from : "/overview";
}

const showDemoCredentials = import.meta.env.DEV || import.meta.env.VITE_SHOW_DEMO_CREDENTIALS === "true";

export function LoginPage() {
  const { status, signIn, notice, clearNotice } = useSession();
  const navigate = useNavigate();
  const target = useRedirectTarget();
  const { busy, formError, run } = useAuthForm();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  if (status === "authenticated") return <Navigate to={target} replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: Errors = {};
    if (!EMAIL.test(email.trim())) next.email = "Enter a valid email address.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    if (Object.keys(next).length) return;
    clearNotice();
    void run(async () => {
      await signIn(email, password);
      navigate(target, { replace: true });
    });
  };

  return (
    <AuthLayout
      title="Sign in"
      description="Access your Threshold workspaces."
      footer={
        <>
          <span>
            New to Threshold? <Link to="/register">Create a workspace</Link>
          </span>
          <span>
            Have an invitation? <Link to="/join">Join a team</Link>
          </span>
        </>
      }
    >
      {notice && <Callout tone="warning">{notice}</Callout>}
      <form className="stack" onSubmit={submit} noValidate>
        <TextField label="Email" type="email" autoComplete="email" value={email} error={errors.email} onChange={(e) => setEmail(e.target.value)} autoFocus />
        <SecretField label="Password" autoComplete="current-password" value={password} error={errors.password} onChange={(e) => setPassword(e.target.value)} />
        <FormError message={formError} />
        <Button variant="primary" type="submit" loading={busy} className="btn--block">
          Sign in
        </Button>
      </form>
      {showDemoCredentials && (
        <div className="demo-hint">
          <div>
            <div className="demo-hint__title">Local demo workspace</div>
            <div className="muted small">Seeded by the repository's demo script.</div>
          </div>
          <Button
            size="sm"
            onClick={() => {
              setEmail("owner@acme-demo.example.com");
              setPassword("demo1234");
              setErrors({});
            }}
          >
            Fill credentials
          </Button>
        </div>
      )}
    </AuthLayout>
  );
}

export function RegisterPage() {
  const { status, register } = useSession();
  const navigate = useNavigate();
  const { busy, formError, run } = useAuthForm();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", organization_name: "", organization_slug: "" });
  const [slugEdited, setSlugEdited] = useState(false);
  const [errors, setErrors] = useState<Errors>({});

  if (status === "authenticated") return <Navigate to="/overview" replace />;

  const set = (key: keyof typeof form, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: Errors = {};
    if (form.full_name.trim().length < 2) next.full_name = "Enter your full name.";
    if (!EMAIL.test(form.email.trim())) next.email = "Enter a valid email address.";
    if (form.password.length < 8) next.password = "Use at least 8 characters.";
    if (form.password.length > 72) next.password = "Use 72 characters or fewer.";
    if (form.organization_name.trim().length < 2) next.organization_name = "Enter a workspace name.";
    if (!SLUG.test(form.organization_slug) || form.organization_slug.length < 2) next.organization_slug = "Use lowercase letters, numbers and single hyphens.";
    setErrors(next);
    if (Object.keys(next).length) return;
    void run(async () => {
      await register({ ...form, full_name: form.full_name.trim(), organization_name: form.organization_name.trim() });
      navigate("/overview", { replace: true });
    });
  };

  return (
    <AuthLayout
      title="Create your workspace"
      description="Start a new Threshold workspace. You'll be its owner."
      footer={
        <span>
          Already have an account? <Link to="/login">Sign in</Link>
        </span>
      }
    >
      <form className="stack" onSubmit={submit} noValidate>
        <TextField label="Full name" autoComplete="name" value={form.full_name} error={errors.full_name} onChange={(e) => set("full_name", e.target.value)} autoFocus />
        <TextField label="Work email" type="email" autoComplete="email" value={form.email} error={errors.email} onChange={(e) => set("email", e.target.value)} />
        <SecretField label="Password" autoComplete="new-password" hint="8–72 characters." value={form.password} error={errors.password} onChange={(e) => set("password", e.target.value)} />
        <TextField
          label="Workspace name"
          value={form.organization_name}
          error={errors.organization_name}
          onChange={(e) => {
            set("organization_name", e.target.value);
            if (!slugEdited) set("organization_slug", slugify(e.target.value));
          }}
        />
        <TextField
          label="Workspace URL slug"
          className="mono"
          value={form.organization_slug}
          error={errors.organization_slug}
          onChange={(e) => {
            setSlugEdited(true);
            set("organization_slug", e.target.value.toLowerCase());
          }}
        />
        <FormError message={formError} />
        <Button variant="primary" type="submit" loading={busy} className="btn--block">
          Create workspace
        </Button>
      </form>
    </AuthLayout>
  );
}

export function JoinPage() {
  const { status, join } = useSession();
  const navigate = useNavigate();
  const { busy, formError, run } = useAuthForm();
  const [form, setForm] = useState({ invitation_token: "", email: "", full_name: "", password: "" });
  const [errors, setErrors] = useState<Errors>({});

  if (status === "authenticated") return <Navigate to="/overview" replace />;

  const set = (key: keyof typeof form, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: Errors = {};
    if (form.invitation_token.trim().length < 20) next.invitation_token = "Paste the full invitation token.";
    if (!EMAIL.test(form.email.trim())) next.email = "Enter the email address the invitation was sent to.";
    if (form.full_name.trim() && form.full_name.trim().length < 2) next.full_name = "Use at least 2 characters.";
    if (form.password.length < 8) next.password = "Use at least 8 characters.";
    setErrors(next);
    if (Object.keys(next).length) return;
    void run(async () => {
      await join({ invitation_token: form.invitation_token.trim(), email: form.email, password: form.password, full_name: form.full_name.trim() || null });
      navigate("/overview", { replace: true });
    });
  };

  return (
    <AuthLayout
      title="Join a team"
      description="Use the invitation token an admin shared with you."
      footer={
        <span>
          Already a member? <Link to="/login">Sign in</Link>
        </span>
      }
    >
      <form className="stack" onSubmit={submit} noValidate>
        <SecretField label="Invitation token" value={form.invitation_token} error={errors.invitation_token} onChange={(e) => set("invitation_token", e.target.value)} autoFocus />
        <TextField label="Email" type="email" autoComplete="email" hint="Must match the invited address." value={form.email} error={errors.email} onChange={(e) => set("email", e.target.value)} />
        <TextField label="Full name" autoComplete="name" optional hint="Required only if you're new to Threshold." value={form.full_name} error={errors.full_name} onChange={(e) => set("full_name", e.target.value)} />
        <SecretField label="Password" autoComplete="new-password" hint="Set a password, or enter your existing one." value={form.password} error={errors.password} onChange={(e) => set("password", e.target.value)} />
        <FormError message={formError} />
        <Button variant="primary" type="submit" loading={busy} className="btn--block">
          Join workspace
        </Button>
      </form>
    </AuthLayout>
  );
}
