import { apiClient } from '@/lib/api/client';
import {
  SecretRefListSchema,
  SecretRefSchema,
  RotateSecretResponseSchema,
} from './schemas';
import type { SecretRef, CreateSecretRequest, RotateSecretResponse } from './schemas';

export async function fetchSecrets(): Promise<SecretRef[]> {
  const data = await apiClient.get('/secrets');
  return SecretRefListSchema.parse(data);
}

/**
 * Creates a secret. The `value` field is sent to BFF and NEVER
 * returned or stored in any client-side state after the request completes.
 */
export async function createSecret(payload: CreateSecretRequest): Promise<SecretRef> {
  const data = await apiClient.post('/secrets', payload);
  return SecretRefSchema.parse(data);
}

export async function rotateSecret(id: string, newValue: string): Promise<RotateSecretResponse> {
  const data = await apiClient.post(`/secrets/${id}/rotate`, { value: newValue });
  return RotateSecretResponseSchema.parse(data);
}

export async function deleteSecret(id: string): Promise<void> {
  await apiClient.delete(`/secrets/${id}`);
}
