/**
 * RigpaLmsRibbon — always-visible top ribbon when Forge-OH runs
 * in Rigpa-LMS plugin mode. Shows course/lesson context, task type
 * selector, audience chip, and artifact packaging action.
 *
 * Feature-flagged: NEXT_PUBLIC_FEATURE_RIGPA_LMS_ENABLED
 * Iframe-safe: no fixed positioning — ribbon is inside normal flow.
 */
'use client';

import React, { useState } from 'react';
import { useRigpaLmsStore } from './store';
import { packageArtifactsToLms } from './api';
import type { RigpaTaskType } from '@/lib/schemas/rigpa-lms';
import styles from './RigpaLmsRibbon.module.css';

const TASK_TYPE_LABELS: Record<RigpaTaskType, string> = {
  authoring: 'Author Content',
  'exercise-gen': 'Generate Exercise',
  'code-review': 'Review Code',
  assessment: 'Assessment',
  refactor: 'Refactor',
};

const AUDIENCE_LABELS = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
} as const;

interface RigpaLmsRibbonProps {
  /** Current run ID for artifact packaging */
  runId?: string;
  /** Artifact IDs available to package back to LMS */
  availableArtifactIds?: string[];
}

export function RigpaLmsRibbon({ runId, availableArtifactIds = [] }: RigpaLmsRibbonProps) {
  const { context, ribbonVisible, pluginMode } = useRigpaLmsStore();
  const [packaging, setPackaging] = useState(false);
  const [packageResult, setPackageResult] = useState<string | null>(null);

  const enabled = process.env.NEXT_PUBLIC_FEATURE_RIGPA_LMS_ENABLED === 'true';
  if (!enabled || !ribbonVisible || !pluginMode || !context) return null;

  const handlePackage = async () => {
    if (!runId || availableArtifactIds.length === 0) return;
    setPackaging(true);
    setPackageResult(null);
    try {
      const results = await packageArtifactsToLms({
        runId,
        artifactIds: availableArtifactIds,
        targetType: context.taskType === 'exercise-gen' ? 'exercise'
          : context.taskType === 'code-review' ? 'feedback-record'
          : context.taskType === 'authoring' ? 'lesson-content'
          : context.taskType === 'assessment' ? 'quiz'
          : 'starter-kit',
        courseId: context.courseId,
        moduleId: context.moduleId,
        lessonId: context.lessonId,
      });
      const packaged = results.filter(r => r.status === 'packaged').length;
      setPackageResult(`${packaged} of ${results.length} artifact${results.length !== 1 ? 's' : ''} sent to LMS`);
    } catch (err) {
      setPackageResult('Package failed — see console');
      console.error('[Forge] LMS package error', err);
    } finally {
      setPackaging(false);
    }
  };

  const { courseId, moduleId, lessonId, taskType, pedagogicalContext } = context;

  return (
    <div
      className={styles.ribbon}
      role="banner"
      aria-label="Rigpa-LMS course context"
      data-testid="rigpa-lms-ribbon"
    >
      {/* Left: course breadcrumb */}
      <div className={styles.breadcrumb}>
        <span className={styles.courseId} title={`Course: ${courseId}`}>
          {courseId}
        </span>
        {moduleId && (
          <>
            <span className={styles.sep} aria-hidden>›</span>
            <span className={styles.moduleId}>{moduleId}</span>
          </>
        )}
        {lessonId && (
          <>
            <span className={styles.sep} aria-hidden>›</span>
            <span className={styles.lessonId}>{lessonId}</span>
          </>
        )}
      </div>

      {/* Center: task type badge + audience chip */}
      <div className={styles.center}>
        <span className={styles.taskBadge} data-task={taskType}>
          {TASK_TYPE_LABELS[taskType]}
        </span>
        <span
          className={styles.audienceChip}
          data-audience={pedagogicalContext.audience}
          aria-label={`Audience: ${AUDIENCE_LABELS[pedagogicalContext.audience]}`}
        >
          {AUDIENCE_LABELS[pedagogicalContext.audience]}
        </span>
      </div>

      {/* Right: package action + result */}
      <div className={styles.actions}>
        {packageResult && (
          <span className={styles.packageResult} role="status">
            {packageResult}
          </span>
        )}
        <button
          className={styles.packageBtn}
          onClick={handlePackage}
          disabled={packaging || !runId || availableArtifactIds.length === 0}
          aria-label="Package artifacts back to LMS"
          aria-busy={packaging}
        >
          {packaging ? 'Sending…' : 'Send to LMS'}
        </button>
      </div>
    </div>
  );
}
