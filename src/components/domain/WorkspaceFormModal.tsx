'use client';
import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { CreateWorkspaceSchema, type CreateWorkspace } from '@/lib/schemas/workspace';
import { useCreateWorkspace, useUpdateWorkspace, useWorkspace } from '@/features/workspaces/hooks';
import styles from './WorkspaceFormModal.module.css';

export interface WorkspaceFormModalProps {
  open: boolean;
  editingId?: string | null;
  onClose: () => void;
}

/**
 * Stage 6: single form for local workspaces. Fields: name (required),
 * path (optional — BFF derives one under FORGE_WORKSPACES_ROOT if omitted),
 * description (optional, cosmetic — not persisted by agent-server).
 */
export const WorkspaceFormModal: React.FC<WorkspaceFormModalProps> = ({ open, editingId, onClose }) => {
  const { data: existing } = useWorkspace(editingId ?? '');
  const createMutation = useCreateWorkspace();
  const updateMutation = useUpdateWorkspace();

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<CreateWorkspace>({
    resolver: zodResolver(CreateWorkspaceSchema),
    defaultValues: { type: 'local', envVars: [] },
  });

  useEffect(() => {
    if (existing) {
      reset({
        name: existing.name,
        type: 'local',
        description: existing.description ?? '',
        path: existing.path ?? '',
        envVars: existing.envVars ?? [],
      });
    } else {
      reset({ type: 'local', envVars: [] });
    }
  }, [existing, reset]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const onSubmit = async (data: CreateWorkspace) => {
    if (editingId) {
      await updateMutation.mutateAsync({ id: editingId, ...data });
    } else {
      await createMutation.mutateAsync(data);
    }
    onClose();
  };

  return (
    <div className={styles.backdrop} onClick={onClose} role="dialog" aria-modal="true" aria-label={editingId ? 'Edit Workspace' : 'New Workspace'}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>{editingId ? 'Edit Workspace' : 'New Workspace'}</h2>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">×</button>
        </div>
        <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className={styles.field}>
            <label htmlFor="ws-name" className={styles.label}>Name <span aria-hidden="true">*</span></label>
            <input id="ws-name" className={styles.input} {...register('name')} placeholder="my-workspace" />
            {errors.name && <span className={styles.error}>{errors.name.message}</span>}
          </div>

          <div className={styles.field}>
            <label htmlFor="ws-path" className={styles.label}>Path</label>
            <input
              id="ws-path"
              className={styles.input}
              {...register('path')}
              placeholder="/absolute/path/to/workspace (optional — derived from name if empty)"
            />
            {errors.path && <span className={styles.error}>{errors.path.message}</span>}
          </div>

          <div className={styles.field}>
            <label htmlFor="ws-desc" className={styles.label}>Description</label>
            <input id="ws-desc" className={styles.input} {...register('description')} placeholder="Optional description" />
          </div>

          <input type="hidden" value="local" {...register('type')} />

          <div className={styles.footer}>
            <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
            <button type="submit" className={styles.submitBtn} disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : editingId ? 'Save Changes' : 'Create Workspace'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
