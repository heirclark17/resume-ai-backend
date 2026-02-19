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

## Meal Plan Image Generation (Fixed Feb 19, 2026)
- **Issue**: Food images regenerated with AI every time user changed days
  - Root cause: Images generated in background AFTER meal plan displayed
  - If user switched days before background completed → meals had no imageUrl
  - MealCard useEffect triggered DALL-E regeneration for meals without imageUrl
- **Fix**: Implemented Option 1 - Upfront batch image generation
  - Generate ALL 21-28 DALL-E images BEFORE showing meal plan
  - Show loading progress: "Generating food photos... X/Y"
  - Only setState once with complete plan (includes all images)
  - Cache and sync complete plan (with images) in one operation
- **Flow**: AI generates plan → Generate all images → Show complete UI → User browses days (no regeneration)
- **Key Files**:
  - `contexts/MealPlanContext.tsx` - generateAIMealPlan() moved image gen before setState
  - `components/mealPlan/MealCard.tsx` - Added logging for pre-generated vs fallback images

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
- **Timeline Display**: Changed from 6 AM start to wake time start
  - First changed from 6 AM to 12 AM (midnight)
  - Then updated to start at user's wake time from preferences
  - Updated 4 files: TimeSlotGrid, TimeBlockCard, CurrentTimeIndicator, DailyTimelineView
  - All positioning now relative to wake time with wraparound for late-night blocks
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
  - Optimized for speed: temperature 0.7→0.3, max_tokens 2000→800 (2-3x faster)
- **Buffer Block Removal** (Feb 16, 2026):
  - User requested no visible buffer blocks: "i dont need the buffer times scheduled"
  - Updated AI prompt instruction #10: "DO NOT create separate 'buffer' blocks - just leave gaps"
  - Disabled `addBufferTimes()` call in schedulingEngine.ts algorithmic fallback
  - Both AI and algorithmic scheduling now leave natural gaps without visible buffers
- **Block Filtering** (Feb 16, 2026):
  - Removed workout and meal_prep blocks from calendar display
  - Only show: sleep, meal_eating, calendar_event, and fasting blocks
  - Keeps calendar cleaner and focused on key activities
- **Single-Day Regeneration** (Feb 16, 2026):
  - Initial generation creates entire week (7 days) with AI
  - Refresh button now regenerates only the selected day
  - Added `regenerateSingleDay(date)` action to DayPlannerContext
  - Preserves other days in weekly plan, only updates selected day
  - No meals during fasting hours enforced by both AI and algorithmic scheduling
- **Key Files**:
  - `services/aiSchedulingService.ts` - AI scheduling with GPT-4.1-mini
  - `services/schedulingEngine.ts` - Algorithmic fallback with buffer removal and eating window enforcement
  - `contexts/DayPlannerContext.tsx` - AI integration, weekly generation, single-day regeneration
  - `components/planner/timeline/` - Timeline display components with wake time positioning
  - `app/(tabs)/planner.tsx` - Refresh button calls regenerateSingleDay

## Saved Meals Page Enhancements (Feb 17, 2026)
- **Image Caching**: Replaced React Native Image with expo-image
  - Meal photos now persist in memory and disk cache
  - No constant reloading when scrolling or navigating
  - cachePolicy="memory-disk" for optimal performance
  - 200ms fade-in transition on first load
- **View Recipe Feature**: Added instant recipe viewing with no loading
  - Recipe button next to meal type badge on every meal card
  - Full-screen modal with ingredients, instructions, nutrients
  - All data stored in database when meal is saved (no AI fetching)
  - Liquid glass modal design with BlurView
  - Ingredients and instructions already in saved_meals table
  - Key files: `app/(tabs)/saved-meals.tsx`

## DaySelector Redesign (Feb 19, 2026)
- **Issue**: Calendar strip needed premium iOS 26 Liquid Glass aesthetic with refined minimalism
- **Evolution**: Two iterations of visual refinement
  - **First iteration**: 72px→96px width, basic frosted glass
  - **Second iteration** (latest): 96px→**108px** width, refined minimalist aesthetic
- **Final Design** (Refined Minimalist with Sculptural Depth):
  - **Card dimensions**: 108x148px with 16px gap (breathing room)
  - **Sculptural shadows**: Softer, diffuse shadows (opacity 0.08, radius 16px)
  - **Typography hierarchy**: Day numbers **42px** (SF Pro Rounded), letter-spacing 2.0
  - **Frosted glass**: Enhanced blur intensity (70 for unselected, 100 for selected)
  - **Selection state**: Subtle 1.03 scale, stronger color overlays (0.40 cheat, 0.32 regular)
  - **Cheat badge**: Premium pill design (12px radius, larger icon 12px)
  - **Motion**: Better press feedback (0.7 activeOpacity)
  - **Design philosophy**: Clean lines, generous padding, confident typography, subtle interactions
- **Key Files**:
  - `components/mealPlan/DaySelector.tsx` - Calendar strip UI

## Grocery List Duplicate Ingredients Fix (Feb 18, 2026)
- **Issue**: Same ingredients appearing multiple times in grocery list instead of aggregating
- **Root Causes**:
  - AI returning ingredient name variations: "chicken breast" vs "boneless chicken breast"
  - AI returning category variations: "Protein" vs "Proteins" vs "Meat"
  - Descriptive words preventing aggregation: "fresh tomatoes" vs "tomatoes"
- **Fix**: Enhanced normalization in `utils/groceryListGenerator.ts`
  - Added parentheses removal: "(boneless)" → ""
  - Added more descriptors: shredded, cubed, ground, lean
  - Added category normalization: "Proteins"/"Meat" → "Protein", "Vegetables"/"Fruits" → "Produce"
  - Enhanced punctuation removal (periods, commas)
- **Result**: Same ingredients now aggregate with combined totals for accurate Instacart ordering
- **Debugging**: Comprehensive logs show raw ingredients, normalization process, and final categorization
- **Key Files**: `utils/groceryListGenerator.ts` - All aggregation and deduplication logic

## AI Workout Program Engine (COMPLETE - Feb 16, 2026)
- **Status**: ALL 7 PHASES COMPLETE
- **Architecture**:
  - multiWeekPlan holds full program, weeklyPlan is derived view of current week
  - TrainingDay.calendarDate is THE single source of truth for dates
  - Fallback pattern: Try AI first, fall back to algorithmic if fails
  - Backend persists full multi-week plan as JSONB
- **Key Files**:
  - `services/programGenerator.ts` - AI generation with GPT-4.1-mini + JSON response format
  - `services/perplexityResearch.ts` - Perplexity sonar research for optimal programming
  - `services/equipmentSwapper.ts` - Day-level equipment switching
  - `services/weightTrackingStorage.ts` - Progressive overload tracking
  - `contexts/TrainingContext.tsx` - Multi-week state, backend sync, overload auto-logging
  - `app/(tabs)/programs.tsx` - Week X of Y, date display, equipment switch button
  - `components/training/WorkoutCard.tsx` - Overload trend badges (green/yellow/red)
  - `components/training/ExerciseAlternativesModal.tsx` - Grouped by equipment type
  - `backend/server-complete.js` - multi_week_plan JSONB, week index sync
- **Phases Completed**:
  - Phase 1: Program generator rewrite (JSON response, real exercises, alternatives) ✅
  - Phase 2: Perplexity research layer (sonar model, training context) ✅
  - Phase 3: Programs.tsx UI (Week X/Y header, calendar dates, status badges) ✅
  - Phase 4: Calendar integration (date-aware workout blocks, bidirectional nav) ✅
  - Phase 5: Progressive overload (trend badges, auto-logging, weight pre-population) ✅
  - Phase 6: Equipment switching (grouped modal, day-level swap button) ✅
  - Phase 7: Backend schema (multi_week_plan JSONB, PATCH week index, full sync) ✅
