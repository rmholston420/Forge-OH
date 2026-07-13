'use client';
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { derivePlanState } from './derivePlanState';
import type { PlaybackSpeed } from './schemas';

async function fetchRunEvents(runId: string) {
  const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';
  const r = await fetch(`${BASE}/runs/${runId}/events`);
  if (!r.ok) throw new Error('Failed to fetch events');
  return r.json();
}

export function useRunReplay(runId: string) {
  const { data: events = [], isLoading } = useQuery({
    queryKey: ['run-events', runId],
    queryFn: () => fetchRunEvents(runId),
    staleTime: Infinity, // replay data is immutable for completed runs
  });

  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying]       = useState(false);
  const [speed, setSpeed]               = useState<PlaybackSpeed>(1);
  const [isLooping, setIsLooping]       = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const totalEvents = events.length;

  const clearTick = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
  }, []);

  useEffect(() => {
    clearTick();
    if (!isPlaying || totalEvents === 0) return;
    const ms = Math.round(1000 / speed);
    intervalRef.current = setInterval(() => {
      setCurrentIndex(i => {
        if (i >= totalEvents - 1) {
          if (isLooping) return 0;
          setIsPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, ms);
    return clearTick;
  }, [isPlaying, speed, totalEvents, isLooping, clearTick]);

  const play  = useCallback(() => setIsPlaying(true),  []);
  const pause = useCallback(() => setIsPlaying(false), []);
  const scrub = useCallback((idx: number) => {
    setCurrentIndex(Math.max(0, Math.min(idx, totalEvents - 1)));
  }, [totalEvents]);
  const stepBack    = useCallback(() => scrub(currentIndex - 1),  [currentIndex, scrub]);
  const stepForward = useCallback(() => scrub(currentIndex + 1),  [currentIndex, scrub]);
  const jumpToStart = useCallback(() => scrub(0),                  [scrub]);
  const jumpToEnd   = useCallback(() => scrub(totalEvents - 1),   [scrub, totalEvents]);

  const derivedPlanState = useMemo(
    () => derivePlanState(events, currentIndex),
    [events, currentIndex]
  );

  const currentTimestamp = events[currentIndex]?.timestamp;

  return {
    events, isLoading, totalEvents, currentIndex, currentTimestamp,
    isPlaying, speed, isLooping,
    derivedPlanState,
    play, pause, scrub, stepBack, stepForward, jumpToStart, jumpToEnd,
    setSpeed, setIsLooping,
  };
}
