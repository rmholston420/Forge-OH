'use client';
import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { CreateWorkspaceSchema, type CreateWorkspace, type WorkspaceType } from '@/lib/schemas/workspace';
import { useCreateWorkspace, useUpdateWorkspace, useWorkspace } from '@/features/workspaces/hooks';
import styles from './WorkspaceFormModal.module.css';

export interface WorkspaceFormModalProps {
  open: boolean;
  editingId?: string | null;
  onClose: () => void;
}

export const WorkspaceFormModal: React.FC<WorkspaceFormModalProps> = ({ open, editingId, onClose }) => {
  const { data: existing } = useWorkspace(editingId ?? '');
  const createMutation = useCreateWorkspace();
  const updateMutation = useUpdateWorkspace();

  const { register, handleSubmit, reset, watch, formState: { errors, isSubmitting } } = useForm<CreateWorkspace>({
    resolver: zodResolver(CreateWorkspaceSchema),
    defaultValues: { type: 'local', envVars: [] },
  });

  const watchedType = watch('type') as WorkspaceType;

  useEffect(() => {
    if (existing) {
      reset({
        name: existing.name,
        type: existing.type,
        description: existing.description ?? '',
        baseDir: existing.baseDir ?? '',
        dockerImage: existing.dockerImage ?? '',
        remoteUrl: existing.remoteUrl ?? '',
        envVars: existing.envVars,
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
      await updateMutation.mutateAsync({ id: editingId, body: data });
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
            <label htmlFor="ws-type" className={styles.label}>Type <span aria-hidden="true">*</span></label>
            <select id="ws-type" className={styles.input} {...register('type')}>
              <option value="local">Local</option>
              <option value="docker">Docker</option>
              <option value="remote_api">Remote API</option>
            </select>
          </div>

          <div className={styles.field}>
            <label htmlFor="ws-desc" className={styles.label}>Description</label>
            <input id="ws-desc" className={styles.input} {...register('description')} placeholder="Optional description" />
          </div>

          {watchedType === 'local' && (
            <div className={styles.field}>
              <label htmlFor="ws-basedir" className={styles.label}>Base Directory</label>
              <input id="ws-basedir" className={styles.input} {...register('baseDir')} placeholder="/home/user/projects" />
            </div>
          )}

          {watchedType === 'docker' && (
            <div className={styles.field}>
              <label htmlFor="ws-image" className={styles.label}>Docker Image</label>
              <input id="ws-image" className={styles.input} {...register('dockerImage')} placeholder="ubuntu:24.04" />
            </div>
          )}

          {watchedType === 'remote_api' && (
            <div className={styles.field}>
              <label htmlFor="ws-url" className={styles.label}>Remote URL</label>
              <input id="ws-url" className={styles.input} type="url" {...register('remoteUrl')} placeholder="https://api.example.com" />
              {errors.remoteUrl && <span className={styles.error}>{errors.remoteUrl.message}</span>}
            </div>
          )}

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
