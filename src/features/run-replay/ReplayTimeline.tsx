'use client';
import { useEffect, useRef } from 'react';
import { formatDate } from '@/lib/utils/format';

interface Props {
  totalEvents:  number;
  currentIndex: number;
  currentTimestamp?: string;
  onScrub: (idx: number) => void;
  onStepBack: () => void;
  onStepForward: () => void;
}

export function ReplayTimeline({
  totalEvents, currentIndex, currentTimestamp, onScrub, onStepBack, onStepForward,
}: Props) {
  const rangeRef = useRef<HTMLInputElement>(null);

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement && e.target.type !== 'range') return;
      if (e.key === 'ArrowLeft')  { e.preventDefault(); e.shiftKey ? onScrub(currentIndex - 10) : onStepBack(); }
      if (e.key === 'ArrowRight') { e.preventDefault(); e.shiftKey ? onScrub(currentIndex + 10) : onStepForward(); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [currentIndex, onScrub, onStepBack, onStepForward]);

  return (
    <div className="replay-timeline" role="group" aria-label="Replay timeline">
      <input
        ref={rangeRef}
        type="range"
        min={0}
        max={Math.max(0, totalEvents - 1)}
        value={currentIndex}
        onChange={e => onScrub(Number(e.target.value))}
        className="replay-scrubber"
        aria-label={`Event ${currentIndex + 1} of ${totalEvents}`}
        aria-valuemin={0}
        aria-valuemax={totalEvents - 1}
        aria-valuenow={currentIndex}
      />
      <div className="replay-timeline-meta">
        <span className="replay-counter">
          {currentIndex + 1} / {totalEvents}
        </span>
        {currentTimestamp && (
          <time className="replay-timestamp" dateTime={currentTimestamp}>
            {formatDate(currentTimestamp)}
          </time>
        )}
      </div>
    </div>
  );
}
