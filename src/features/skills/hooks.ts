'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchSkills } from './api';

/**
 * useSkills — list all user + project skills available to the running BFF.
 * Cached under queryKey ['skills', scopes] so scope toggles refresh cleanly.
 */
export function useSkills(params?: {
  includeUser?: boolean;
  includeProject?: boolean;
}) {
  return useQuery({
    queryKey: ['skills', params ?? {}],
    queryFn: () => fetchSkills(params),
    staleTime: 30_000,
  });
}
