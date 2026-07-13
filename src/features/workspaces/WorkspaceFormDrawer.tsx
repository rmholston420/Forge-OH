'use client';
import { useEffect } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { CreateWorkspaceSchema, type CreateWorkspaceRequest } from './schemas';
import { useCreateWorkspace, useUpdateWorkspace, useWorkspace } from './hooks';
import { useWorkspacesStore } from './store';

export function WorkspaceFormDrawer() {
  const { drawerOpen, editingId, closeDrawer } = useWorkspacesStore();
  const { data: existing } = useWorkspace(editingId ?? '');
  const create = useCreateWorkspace();
  const update = useUpdateWorkspace();

  const { register, handleSubmit, reset, control,
          formState: { errors, isSubmitting } } =
    useForm<CreateWorkspaceRequest>({
      resolver: zodResolver(CreateWorkspaceSchema),
      defaultValues: { type: 'local', envVars: [] },
    });

  const { fields, append, remove } = useFieldArray({ control, name: 'envVars' });

  // Populate form when editing
  useEffect(() => {
    if (existing) {
      reset({ name: existing.name, description: existing.description,
               type: existing.type,  envVars: existing.envVars,
               agentPresetId: existing.agentPresetId });
    } else {
      reset({ type: 'local', envVars: [] });
    }
  }, [existing, reset]);

  async function onSubmit(data: CreateWorkspaceRequest) {
    if (editingId) {
      await update.mutateAsync({ id: editingId, ...data });
    } else {
      await create.mutateAsync(data);
    }
    closeDrawer();
  }

  if (!drawerOpen) return null;

  return (
    <div className="drawer-overlay" role="dialog" aria-modal="true"
         aria-label={editingId ? 'Edit workspace' : 'New workspace'}>
      <div className="drawer">
        <div className="drawer-header">
          <h2>{editingId ? 'Edit workspace' : 'New workspace'}</h2>
          <button className="drawer-close" onClick={closeDrawer}
                  aria-label="Close drawer">&times;</button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="drawer-form">
          <div className="form-field">
            <label htmlFor="ws-name">Name</label>
            <input id="ws-name" {...register('name')} />
            {errors.name && <span className="field-error">{errors.name.message}</span>}
          </div>

          <div className="form-field">
            <label htmlFor="ws-desc">Description</label>
            <textarea id="ws-desc" rows={2} {...register('description')} />
          </div>

          <div className="form-field">
            <label htmlFor="ws-type">Type</label>
            <select id="ws-type" {...register('type')}>
              <option value="local">Local</option>
              <option value="docker">Docker</option>
              <option value="e2b">E2B</option>
              <option value="modal">Modal</option>
            </select>
          </div>

          <fieldset className="form-fieldset">
            <legend>Environment variables</legend>
            {fields.map((field, idx) => (
              <div key={field.id} className="env-var-row">
                <input placeholder="KEY" {...register(`envVars.${idx}.key`)} />
                <input placeholder="value" {...register(`envVars.${idx}.value`)} />
                <button type="button" onClick={() => remove(idx)}
                        aria-label="Remove variable">×</button>
              </div>
            ))}
            <button type="button" className="btn btn-sm btn-ghost"
                    onClick={() => append({ key: '', value: '', masked: true })}>
              + Add variable
            </button>
          </fieldset>

          <div className="drawer-footer">
            <button type="button" className="btn btn-ghost" onClick={closeDrawer}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : editingId ? 'Save changes' : 'Create workspace'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
