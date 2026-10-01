import { useMemo } from "react";
import { useActions, useWorkflows } from "@/hooks/queries";
import type { ActionSummary, WorkflowDefinition } from "@/types/api";

/**
 * The executions endpoint returns only `workflow_id`, so names and triggers
 * come from the workflows list, and external-action state from the action ledger.
 */
export function useExecutionLookups() {
  const workflows = useWorkflows();
  const actions = useActions();

  const workflowById = useMemo(() => new Map<string, WorkflowDefinition>((workflows.data ?? []).map((w) => [w.id, w])), [workflows.data]);

  const actionByExecution = useMemo(() => {
    const map = new Map<string, ActionSummary>();
    // Newest first from the API; keep the latest action per execution.
    for (const action of actions.data ?? []) if (!map.has(action.execution_id)) map.set(action.execution_id, action);
    return map;
  }, [actions.data]);

  return { workflowById, actionByExecution, workflows: workflows.data ?? [] };
}
