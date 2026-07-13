'use client';
import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/core/Button';
import { Banner } from '@/components/core/Banner';
import { useCreateRun } from '@/features/runs/hooks';
import { useAgentPresets } from '@/features/runs/hooks';
import { useWorkspaces } from '@/features/workspaces/hooks';
import { CreateRunRequestSchema, type CreateRunRequest } from '@/features/runs/schemas';
import styles from './NewRunComposer.module.css';

export interface NewRunComposerProps {
  onSuccess?: (runId: string) => void;
  onCancel?: () => void;
}

function estimateContextLength(text: string) {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return Math.max(trimmed.length, Math.ceil(trimmed.split(/\s+/).length * 4));
}

export const NewRunComposer: React.FC<NewRunComposerProps> = ({ onSuccess, onCancel }) => {
  const { data: presets = [], isLoading: presetsLoading } = useAgentPresets();
  const { data: workspaces = [], isLoading: wsLoading } = useWorkspaces();
  const createRun = useCreateRun();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CreateRunRequest>({
    resolver: zodResolver(CreateRunRequestSchema),
    defaultValues: {
      title: '',
      contextPrompt: '',
      agentPresetId: '',
      workspaceId: '',
      taskComplexity: 'agentic',
      contextLength: 0,
    },
  });

  useEffect(() => {
    if (presets.length > 0) {
      setValue('agentPresetId', presets[0]?.id ?? '', { shouldValidate: true });
    }
  }, [presets, setValue]);

  useEffect(() => {
    if (workspaces.length > 0) {
      setValue('workspaceId', workspaces[0]?.id ?? '', { shouldValidate: true });
    }
  }, [workspaces, setValue]);

  const titleValue = watch('title') ?? '';
  const estimatedContextLength = estimateContextLength(titleValue);

  useEffect(() => {
    setValue('contextLength', estimatedContextLength, { shouldValidate: false, shouldDirty: false });
    setValue('contextPrompt', titleValue, { shouldValidate: false, shouldDirty: false });
  }, [estimatedContextLength, titleValue, setValue]);

  const onSubmit = async (data: CreateRunRequest) => {
    const run = await createRun.mutateAsync({
      ...data,
      contextPrompt: data.contextPrompt || data.title,
      contextLength: data.contextLength ?? estimateContextLength(data.title),
    });
    onSuccess?.(run.id);
  };

  const noWorkspace = !wsLoading && workspaces.length === 0;

  return (
    <form className={styles.composer} onSubmit={handleSubmit(onSubmit)} noValidate>
      <h2 className={styles.title}>New Run</h2>

      {noWorkspace && (
        <Banner variant="warning">
          No workspaces available. Add a workspace in Settings before launching a run.
        </Banner>
      )}

      {createRun.error && (
        <Banner variant="error">Failed to create run. Please try again.</Banner>
      )}

      <div className={styles.field}>
        <label className={styles.label} htmlFor="run-title">Task description</label>
        <textarea
          id="run-title"
          className={styles.textarea}
          placeholder="Describe what you want the agent to do…"
          rows={3}
          aria-describedby={errors.title ? 'run-title-error' : 'run-routing-hint'}
          aria-invalid={!!errors.title}
          {...register('title')}
        />
        {errors.title && (
          <span id="run-title-error" className={styles.fieldError} role="alert">{errors.title.message}</span>
        )}
        {!errors.title && (
          <span id="run-routing-hint" className={styles.helpText}>
            Estimated routing context: {estimatedContextLength} tokens
          </span>
        )}
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="run-preset">Agent preset</label>
          <select id="run-preset" className={styles.select} disabled={presetsLoading} {...register('agentPresetId')}>
            {presetsLoading && <option value="">Loading…</option>}
            {!presetsLoading && presets.length === 0 && <option value="">No presets</option>}
            {presets.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="run-workspace">Workspace</label>
          <select id="run-workspace" className={styles.select} disabled={wsLoading || noWorkspace} {...register('workspaceId')}>
            {wsLoading && <option value="">Loading…</option>}
            {!wsLoading && noWorkspace && <option value="">No workspaces</option>}
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>{w.name} ({w.type})</option>
            ))}
          </select>
        </div>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="run-complexity">Routing profile</label>
        <select id="run-complexity" className={styles.select} {...register('taskComplexity')}>
          <option value="agentic">Agentic — deeper reasoning, planning, orchestration</option>
          <option value="simple">Simple — lighter execution, shorter tasks</option>
        </select>
      </div>

      <input type="hidden" {...register('contextPrompt')} />
      <input type="hidden" {...register('contextLength', { valueAsNumber: true })} />

      <div className={styles.actions}>
        {onCancel && <Button type="button" variant="tertiary" onClick={onCancel}>Cancel</Button>}
        <Button
          type="submit"
          variant="primary"
          loading={isSubmitting || createRun.isPending}
          disabled={noWorkspace}
        >
          Launch Run
        </Button>
      </div>
    </form>
  );
};
