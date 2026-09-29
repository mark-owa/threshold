import React, { useState } from "react";

interface CreateWorkspacePanelProps {
  onCreate: (name: string, slug: string) => void;
}

export function CreateWorkspacePanel({ onCreate }: CreateWorkspacePanelProps) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  return (
    <section className="panel create-workspace">
      <div><h2>Create another workspace</h2><p>New workspaces are isolated trial tenants. Demo scenarios will not be available inside them.</p></div>
      <div className="inline-form"><input value={name} onChange={e => setName(e.target.value)} placeholder="Workspace name" /><input value={slug} onChange={e => setSlug(e.target.value.toLowerCase().replace(/\s+/g, "-"))} placeholder="workspace-slug" /><button onClick={() => onCreate(name, slug)}>Create</button></div>
    </section>
  );
}
