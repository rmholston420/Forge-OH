'use client';
import type { PlaybackSpeed } from './schemas';

const SPEEDS: PlaybackSpeed[] = [0.25, 0.5, 1, 2, 4];

interface Props {
  isPlaying:    boolean;
  speed:        PlaybackSpeed;
  isLooping:    boolean;
  currentIndex: number;
  totalEvents:  number;
  onPlay:        () => void;
  onPause:       () => void;
  onStepBack:    () => void;
  onStepForward: () => void;
  onJumpStart:   () => void;
  onJumpEnd:     () => void;
  onSetSpeed:    (s: PlaybackSpeed) => void;
  onSetLooping:  (v: boolean) => void;
}

export function PlaybackControls({
  isPlaying, speed, isLooping, currentIndex, totalEvents,
  onPlay, onPause, onStepBack, onStepForward, onJumpStart, onJumpEnd,
  onSetSpeed, onSetLooping,
}: Props) {
  const atStart = currentIndex === 0;
  const atEnd   = currentIndex >= totalEvents - 1;

  return (
    <div className="playback-controls" role="toolbar" aria-label="Playback controls">
      <button className="btn btn-sm" onClick={onJumpStart} disabled={atStart}
        aria-label="Jump to start">⏮️</button>
      <button className="btn btn-sm" onClick={onStepBack}  disabled={atStart}
        aria-label="Step back">⏪</button>

      <button
        className="btn btn-primary"
        onClick={isPlaying ? onPause : onPlay}
        disabled={atEnd && !isLooping}
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? '⏸️' : '▶️'}
      </button>

      <button className="btn btn-sm" onClick={onStepForward} disabled={atEnd}
        aria-label="Step forward">⏩</button>
      <button className="btn btn-sm" onClick={onJumpEnd}     disabled={atEnd}
        aria-label="Jump to end">⏭️</button>

      <div className="speed-selector" role="group" aria-label="Playback speed">
        {SPEEDS.map(s => (
          <button
            key={s}
            className={`btn btn-sm ${speed === s ? 'btn-active' : 'btn-ghost'}`}
            onClick={() => onSetSpeed(s)}
            aria-pressed={speed === s}
          >
            {s}x
          </button>
        ))}
      </div>

      <button
        className={`btn btn-sm ${isLooping ? 'btn-active' : 'btn-ghost'}`}
        onClick={() => onSetLooping(!isLooping)}
        aria-pressed={isLooping}
        aria-label="Loop playback"
      >
        🔁
      </button>
    </div>
  );
}
