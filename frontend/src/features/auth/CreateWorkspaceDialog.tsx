import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { TextField } from "@/components/ui/Fields";
import { useToast } from "@/components/ui/Toast";
import { slugify } from "@/utils/format";
import { useSession } from "./session";

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function CreateWorkspaceDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { createWorkspace } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slugError = slug && !SLUG_PATTERN.test(slug) ? "Use lowercase letters, numbers and single hyphens." : null;

  const reset = () => {
    setName("");
    setSlug("");
    setSlugEdited(false);
    setError(null);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createWorkspace(name.trim(), slug);
      toast.success("Workspace created", created.name);
      reset();
      onClose();
      navigate("/overview");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Create workspace"
      description="Workspaces isolate data, members and integrations. You'll be the owner."
      busy={busy}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="create-workspace-form" loading={busy} disabled={!name.trim() || !slug || !!slugError}>
            Create workspace
          </Button>
        </>
      }
    >
      <form id="create-workspace-form" className="stack" onSubmit={submit}>
        <TextField
          label="Workspace name"
          value={name}
          maxLength={255}
          autoFocus
          onChange={(e) => {
            setName(e.target.value);
            if (!slugEdited) setSlug(slugify(e.target.value));
          }}
        />
        <TextField
          label="URL slug"
          hint="Unique identifier for this workspace."
          value={slug}
          className="mono"
          error={slugError}
          onChange={(e) => {
            setSlugEdited(true);
            setSlug(e.target.value.toLowerCase());
          }}
        />
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </form>
    </Dialog>
  );
}
