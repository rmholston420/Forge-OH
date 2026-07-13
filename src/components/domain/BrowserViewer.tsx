'use client';
import React, { useEffect, useRef, useCallback } from 'react';
import type { BrowserFrame } from '@/lib/schemas/browser';
import { useBrowserStore } from '@/features/browser/store';
import styles from './BrowserViewer.module.css';

const ACTION_ICON: Record<string, string> = {
  navigate: '🌐', click: '🖱️', type: '⌨️', scroll: '↕️',
  screenshot: '📷', wait: '⏳', hover: '👆', select: '📋',
  keypress: '⌨️', back: '◀️', forward: '▶️',
};

export interface BrowserViewerProps {
  frames: BrowserFrame[];
  isActive?: boolean;
}

export const BrowserViewer: React.FC<BrowserViewerProps> = ({ frames, isActive = false }) => {
  const { selectedFrameId, isPlaying, playheadIndex, setSelectedFrame, setPlaying, setPlayheadIndex } = useBrowserStore();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const currentFrame = selectedFrameId
    ? frames.find((f) => f.id === selectedFrameId)
    : frames[playheadIndex] ?? frames[frames.length - 1];

  const stopPlayback = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = null;
    setPlaying(false);
  }, [setPlaying]);

  useEffect(() => {
    if (!isPlaying) return;
    intervalRef.current = setInterval(() => {
      setPlayheadIndex(Math.min(playheadIndex + 1, frames.length - 1));
      if (playheadIndex >= frames.length - 1) stopPlayback();
    }, 800);
    return () => stopPlayback();
  }, [isPlaying, playheadIndex, frames.length, setPlayheadIndex, stopPlayback]);

  if (!frames.length) {
    return (
      <div className={styles.empty}>
        <span>🌐</span>
        <p>No browser activity recorded yet.</p>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      {/* Screenshot panel */}
      <div className={styles.preview}>
        {currentFrame?.screenshotUrl ? (
          <img
            src={currentFrame.screenshotUrl}
            alt={`Browser screenshot at step ${currentFrame.seq}`}
            className={styles.screenshot}
            loading="lazy"
            width={1280}
            height={800}
          />
        ) : (
          <div className={styles.noScreenshot}>
            <span style={{ fontSize: '2rem' }}>{ACTION_ICON[currentFrame?.action ?? 'navigate'] ?? '🌐'}</span>
            <p>{currentFrame?.action ?? 'No frame'}</p>
            {currentFrame?.url && <code className={styles.url}>{currentFrame.url}</code>}
          </div>
        )}
        {/* Bounding-box overlay */}
        {currentFrame?.boundingBox && (
          <div
            className={styles.bbox}
            style={{
              left: `${(currentFrame.boundingBox.x / 1280) * 100}%`,
              top: `${(currentFrame.boundingBox.y / 800) * 100}%`,
              width: `${(currentFrame.boundingBox.width / 1280) * 100}%`,
              height: `${(currentFrame.boundingBox.height / 800) * 100}%`,
            }}
          />
        )}
      </div>

      {/* Playback controls */}
      <div className={styles.controls}>
        <button className={styles.ctrlBtn} onClick={() => setPlayheadIndex(0)} aria-label="Go to start">⏮</button>
        <button
          className={styles.ctrlBtn}
          onClick={() => setPlayheadIndex(Math.max(0, playheadIndex - 1))}
          aria-label="Previous frame"
        >⏪</button>
        <button
          className={styles.ctrlBtn}
          onClick={() => isPlaying ? stopPlayback() : setPlaying(true)}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >{isPlaying ? '⏸' : '▶️'}</button>
        <button
          className={styles.ctrlBtn}
          onClick={() => setPlayheadIndex(Math.min(frames.length - 1, playheadIndex + 1))}
          aria-label="Next frame"
        >⏩</button>
        <button
          className={styles.ctrlBtn}
          onClick={() => setPlayheadIndex(frames.length - 1)}
          aria-label="Go to end"
        >⏭</button>
        <input
          type="range" min={0} max={Math.max(0, frames.length - 1)} value={playheadIndex}
          className={styles.scrubber}
          onChange={(e) => { stopPlayback(); setPlayheadIndex(Number(e.target.value)); }}
          aria-label="Scrub to frame"
        />
        <span className={styles.counter}>{playheadIndex + 1} / {frames.length}</span>
      </div>

      {/* Frame timeline */}
      <ol className={styles.timeline} role="list">
        {frames.map((frame, i) => (
          <li
            key={frame.id}
            className={[
              styles.frameItem,
              (selectedFrameId === frame.id || (!selectedFrameId && i === playheadIndex))
                ? styles['frameItem--active'] : '',
              frame.error ? styles['frameItem--error'] : '',
            ].filter(Boolean).join(' ')}
            onClick={() => { stopPlayback(); setSelectedFrame(frame.id); setPlayheadIndex(i); }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setSelectedFrame(frame.id)}
            aria-pressed={selectedFrameId === frame.id}
          >
            <span className={styles.frameIcon}>{ACTION_ICON[frame.action] ?? '•'}</span>
            <span className={styles.frameAction}>{frame.action}</span>
            {frame.selector && <code className={styles.frameSelector}>{frame.selector.slice(0, 40)}</code>}
            {frame.error && <span className={styles.frameError}>⚠ {frame.error.slice(0, 40)}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
};
