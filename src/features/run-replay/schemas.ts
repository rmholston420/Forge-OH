import { z } from 'zod';

export const PlaybackSpeedSchema = z.union([
  z.literal(0.25), z.literal(0.5), z.literal(1),
  z.literal(2),   z.literal(4),
]);
export type PlaybackSpeed = z.infer<typeof PlaybackSpeedSchema>;

export const RunReplayStateSchema = z.object({
  runId:          z.string(),
  totalEvents:    z.number().int().min(0),
  currentIndex:   z.number().int().min(0),
  currentTimestamp: z.string().optional(),
  isPlaying:      z.boolean(),
  playbackSpeed:  PlaybackSpeedSchema,
  isLooping:      z.boolean(),
});
export type RunReplayState = z.infer<typeof RunReplayStateSchema>;
