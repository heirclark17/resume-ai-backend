# User Preferences
- **Auto-commit**: Always commit and deploy changes without asking for confirmation
- **Auto-push**: Always push to remote after committing

# Heirclark Health App - Key Learnings

## Project Location
- App: `C:\Users\derri\HeirclarkHealthAppNew\`
- Bash paths: `/c/Users/derri/HeirclarkHealthAppNew/`

## Font System
- **Urbanist** for text/letters, **SF Pro Rounded** for numbers
- Theme.ts `Fonts.numericXXX` constants map to SF Pro Rounded variants
- `NumberText` component (`components/NumberText.tsx`) wraps Text with SF Pro Rounded
- `RoundedNumeral` component is for formatted numeric display with commas/decimals
- **Bug found & fixed**: `numericSemibold` casing mismatch (lowercase 'b' in Theme.ts vs uppercase 'B' in components) - fixed to `numericSemiBold` everywhere

## API Architecture
- Singleton at `services/api.ts` - `import { api } from '../services/api'`
- Railway backend: `https://heirclarkinstacartbackend-production.up.railway.app`
- Backend source: `HeirclarkHealthAppNew/backend/server-complete.js` (JavaScript, NOT TypeScript)
- Railway deploys from: `heirclark17/HeirclarkHealthAppNew` repo (backend in `/backend` subdirectory)
- JWT auth via Bearer token stored in AsyncStorage
- Pattern: backend-first reads, fire-and-forget writes (don't block UI)

## Context Wiring Pattern
```typescript
// READS: backend-first, local fallback
try {
  const data = await api.someReadMethod();
  if (data) { setState(data); return; }
} catch (error) {
  console.error('[ContextName] API fetch error:', error);
}
const localData = await storage.getData();
if (localData) setState(localData);

// WRITES: fire-and-forget after local save
try {
  await api.someWriteMethod(data);
} catch (error) {
  console.error('[ContextName] API sync error:', error);
}
```

## Key Files
- Contexts: `contexts/` - 20 files, 10 needed API wiring
- Agent cards: `components/agents/` - 9 subdirectories
- Tab screens: `app/(tabs)/` - 13 files
- Modals: scattered across components/

## Gotchas
- Home directory glob searches timeout - always use project subdir
- Windows paths in tools, Unix paths in Bash
- `EditMealModal` exists but is never rendered anywhere
- NotificationContext was already wired to API
- **Health Ingest decimal fix (Feb 13, 2026)**: Apple Health sends decimal step counts (e.g., 12111.99875120482) but PostgreSQL step_logs.steps is INTEGER - must use Math.floor(parseFloat()) to round before INSERT
- **App version headers (Feb 13, 2026)**: Backend middleware expects x-app-version and x-app-build-number headers - added to api.ts getHeaders() method using expo-constants to prevent "No app version header found" warnings
- **Decimal removal (Feb 13, 2026)**: Removed all decimals from UI displays - changed .toFixed(1) and .toFixed(2) to Math.round() across 12 components (StepsCard, RestingEnergyCard, DailyFatLossCard, WeightLoggingCard, ProgressPredictionCard, HydrationCard, SleepRecoveryCard, GoalStep, ResultsStep, SuccessScreen, PlanPreviewStep, steps.tsx) - kept 2 decimals for dollar amounts only

## Meal Plan & Recipe System (Fixed Feb 12, 2026)
- **Issue**: AI meal plan generation failed silently when no goals set
- **Fix**: Added goals validation with Alert dialog in `handleAIGenerate()` and `handleGenerate()`
- **UX**: Users now get "Goals Required" alert with "Set Goals" button → navigates to `/goals` tab
- **Recipe Auto-Fetch**: Already implemented via useEffect in MealCard.tsx (lines 80-116)
  - Triggers automatically when "View Recipe" button clicked
  - Fetches from `/api/v1/ai/recipe-details` endpoint
  - Caches result in component state
- **Backend**: Meal plans generate with minimal structure (no ingredients initially)
  - max_tokens: 3500 (reduced from 8000 to prevent truncation)
  - Ingredients/instructions fetched on-demand when user clicks "View Recipe"

## Training Plan Program Selection (Fixed Feb 14, 2026)
- **Issue**: "Start Your Training Plan" button on SuccessScreen didn't generate AI workout plan
  - Root cause: Validation checked `trainingState.selectedProgram` which was always null
  - Onboarding had no step for program selection
  - Alert appeared → user had to navigate to programs tab manually → poor UX
- **Fix**: Added program selection as step 5 in goal wizard (between Nutrition and Review)
  - Created `ProgramSelectionStep.tsx` component with program cards
  - Added `selectedProgramId` and `selectedProgramName` to GoalWizardContext
  - Updated SuccessScreen to check `state.selectedProgramId` from goal wizard
  - Updated `handleStartTrainingPlan` to select program before AI generation
- **Flow**: Goal → Body → Activity → Nutrition → **Program** → Review → Success Screen
  - User selects training program during onboarding (step 5/6)
  - SuccessScreen validates program selection from goal wizard state
  - "Start Your Training Plan" button selects program in TrainingContext
  - AI workout plan generates based on selected program
  - User navigates to programs tab to see generated plan
- **Key Files**:
  - `components/goals/ProgramSelectionStep.tsx` - Program selection UI
  - `contexts/GoalWizardContext.tsx` - Added selectedProgramId/Name fields
  - `app/(tabs)/goals.tsx` - Added step 5, updated from 5 to 6 total steps
  - `components/goals/SuccessScreen.tsx` - Checks goal wizard program selection

## Day Planner Scheduling (Fixed Feb 16, 2026)
- **Timeline Display**: Changed from 6 AM start to 12 AM (midnight) start
  - Updated 4 files: TimeSlotGrid, TimeBlockCard, CurrentTimeIndicator, DailyTimelineView
  - Removed all 6 AM offsets from position calculations
- **Meal Scheduling Issues**: Fixed meals scheduling at wrong times (dinner at 6:15 AM, breakfast at 8 PM)
  - Root cause #1: Fasting window block added even on cheat/flex days
  - Root cause #2: findAvailableSlot didn't respect IF eating window boundaries
  - Root cause #3: Aggressive buffer times pushed meals too late
- **Fixes Applied**:
  - Skip fasting block on cheat days: `if (isFasting && !isCheatDay)` check before addFastingBlock
  - Added `eatingWindow` parameter to findAvailableSlot with boundary checks
  - Reduced buffer times: 60→15 min after sleep, 45→15 after meetings, 30→15 before workouts
  - Changed breakfast default from wake+30 to wake+15 minutes
  - Fasting window color: Changed to transparent blue (#4A90E240)
- **AI-Powered Scheduling**: Implemented full AI scheduling using GPT-4.1-mini
  - Created `services/aiSchedulingService.ts` with comprehensive prompt
  - AI considers: meals, workouts, calendar events, IF windows, recovery status, sleep times
  - Returns structured JSON with TimeBlock format, reasoning, and warnings
  - Fallback pattern: Try AI first, fall back to algorithmic on error
  - Made `generateDailyTimeline` async to support AI calls
- **Buffer Block Removal** (Feb 16, 2026):
  - User requested no visible buffer blocks: "i dont need the buffer times scheduled"
  - Updated AI prompt instruction #10: "DO NOT create separate 'buffer' blocks - just leave gaps"
  - Disabled `addBufferTimes()` call in schedulingEngine.ts algorithmic fallback
  - Both AI and algorithmic scheduling now leave natural gaps without visible buffers
- **Key Files**:
  - `services/aiSchedulingService.ts` - AI scheduling with GPT-4.1-mini
  - `services/schedulingEngine.ts` - Algorithmic fallback with buffer removal
  - `contexts/DayPlannerContext.tsx` - AI integration with fallback pattern
  - `components/planner/timeline/` - Timeline display components (4 files)
