# Slice 5C — Rigpa-LMS Plugin Integration Layer

## Routes
- `POST /api/lms/context` — inject `RigpaAgentLaunchContext`
- `GET /api/lms/context/:sessionId` — fetch active LMS context
- `POST /api/lms/package` — package artifacts back to LMS

## Feature Flags
- BFF: `FEATURE_RIGPA_LMS_ENABLED`
- Frontend: `NEXT_PUBLIC_FEATURE_RIGPA_LMS_ENABLED`

## Context Injection Shape
```json
{
  "userId": "usr_001",
  "courseId": "RIGPA-CS101",
  "moduleId": "M3-Functions",
  "lessonId": "L2-Closures",
  "taskType": "exercise-gen",
  "permissions": { "canWriteRepo": true, "canRunShell": true, "canOpenPR": false },
  "pedagogicalContext": {
    "audience": "beginner",
    "learningGoals": ["Understand closure scope"],
    "styleGuide": "Use ES6 syntax."
  }
}
```

## Iframe Safety
Ribbon uses `position: relative` — never `fixed` or `sticky`. The LMS iframe
host controls the scroll context.

## ADR
See `.openhands/context/decisions/003-rigpa-lms-plugin-architecture.md`
