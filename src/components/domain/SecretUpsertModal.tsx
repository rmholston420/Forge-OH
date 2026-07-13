'use client';
import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { UpsertSecretSchema, type UpsertSecret } from '@/lib/schemas/secret';
import { useUpsertSecret } from '@/features/secrets/hooks';
import styles from './WorkspaceFormModal.module.css'; // reuse form modal styles

export interface SecretUpsertModalProps {
  open: boolean;
  onClose: () => void;
}

export const SecretUpsertModal: React.FC<SecretUpsertModalProps> = ({ open, onClose }) => {
  const upsertMutation = useUpsertSecret();
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<UpsertSecret>({
    resolver: zodResolver(UpsertSecretSchema),
    defaultValues: { scope: 'global' },
  });

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const onSubmit = async (data: UpsertSecret) => {
    await upsertMutation.mutateAsync(data);
    reset();
    onClose();
  };

  return (
    <div className={styles.backdrop} onClick={onClose} role="dialog" aria-modal="true" aria-label="Add Secret">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>Add Secret</h2>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">×</button>
        </div>
        <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className={styles.field}>
            <label htmlFor="sec-name" className={styles.label}>Name <span aria-hidden="true">*</span></label>
            <input id="sec-name" className={styles.input} {...register('name')} placeholder="MY_API_KEY" />
            {errors.name && <span className={styles.error}>{errors.name.message}</span>}
          </div>
          <div className={styles.field}>
            <label htmlFor="sec-value" className={styles.label}>Value <span aria-hidden="true">*</span></label>
            <input id="sec-value" type="password" className={styles.input} {...register('value')} placeholder="sk-..." autoComplete="new-password" />
            {errors.value && <span className={styles.error}>{errors.value.message}</span>}
          </div>
          <div className={styles.field}>
            <label htmlFor="sec-scope" className={styles.label}>Scope</label>
            <select id="sec-scope" className={styles.input} {...register('scope')}>
              <option value="global">Global</option>
              <option value="workspace">Workspace</option>
              <option value="run">Run</option>
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor="sec-desc" className={styles.label}>Description</label>
            <input id="sec-desc" className={styles.input} {...register('description')} placeholder="Optional description" />
          </div>
          <div className={styles.footer}>
            <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
            <button type="submit" className={styles.submitBtn} disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : 'Add Secret'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
