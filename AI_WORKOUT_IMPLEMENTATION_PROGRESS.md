# AI Workout Program Engine - Implementation Progress

## Summary

Implementing a comprehensive AI-powered multi-week workout program system for the Heirclark Health App. This document tracks progress against the 6-phase implementation plan.

---

## ✅ Phase 0: Critical Bug Fixes (COMPLETE)

### Bugs Fixed

1. **Equipment Field Mismatch**
   - File: `components/goals/SuccessScreen.tsx` (line 115)
   - Changed: `equipmentAccess` → `availableEquipment`
   - Impact: AI workout guidance now receives correct equipment list from GoalWizardContext

2. **Fasting Window Object Structure**
   - File: `components/goals/PlanPreviewStep.tsx` (line 964)
   - Changed: `state.fastingWindow` → `state.fastingStart && state.fastingEnd`
   - Impact: Fasting section now renders correctly in plan preview

3. **Missing WorkoutCard Render**
   - File: `app/(tabs)/programs.tsx` (line 500)
   - Added: `<WorkoutCard>` component between week navigation and custom workouts
   - Impact: Users can now view and interact with daily workout exercises

**Status:** All 3 bugs fixed and deployed
**Commits:** `b1e73fb`

---

## ✅ Phase 1: Minimal Viable Workout Generation (IN PROGRESS)

### Part 1: Type Extensions (COMPLETE)

**Extended `CompleteTrainingPlan` interface:**
```typescript
interface CompleteTrainingPlan {
  // ... existing fields
  calendarStartDate: string;  // ISO date - Week 1 Day 1 anchor
  currentWeekIndex: number;   // 0-based (0 = week 1, 1 = week 2)
  totalWeeks: number;         // 4, 8, or 12 weeks
}
```

**Extended `TrainingDay` interface:**
```typescript
interface TrainingDay {
  // ... existing fields
  calendarDate: string;  // ISO date (YYYY-MM-DD) - SINGLE SOURCE OF TRUTH
  weekNumber: number;    // Which week of program (1-12)
}
```

**File:** `types/training.ts`
**Commits:** `fa459d5`

---

### Part 2: Program Generator Service (COMPLETE)

**Created:** `services/programGenerator.ts` (374 lines)

**Key Functions:**
- `generateMultiWeekProgram()` - Main AI generation function
- `getMostRecentMonday()` - Calendar alignment helper
- `parseAIProgramOutput()` - AI response parser (placeholder for now)
- `generateFallbackProgram()` - Template-based fallback

**Features:**
- Uses GPT-4.1-mini with 4000 token limit
- Generates 4-12 week programs
- Calendar alignment to most recent Monday
- Fallback to template generation if AI fails
- Placeholder exercise structure (to be enhanced with ExerciseDB integration)

**Current Limitations:**
- Placeholder parsing (needs enhancement to handle actual GPT output)
- Basic exercise structure (needs exercise alternatives from ExerciseDB)
- No progressive overload logic yet

**Commits:** `fa459d5`

---

### Part 3: TrainingContext Multi-Week Support (COMPLETE)

**State Extensions:**
```typescript
interface TrainingState {
  // ... existing fields
  multiWeekPlan: CompleteTrainingPlan | null;
  currentWeekIndex: number;
}
```

**Backward Compatibility Strategy:**
- `multiWeekPlan` holds full program
- `weeklyPlan` auto-synced from `multiWeekPlan[currentWeekIndex]`
- useEffect keeps weeklyPlan in sync with current week
- Existing code using `state.weeklyPlan` continues to work

**Week Navigation Updates:**
- `goToNextWeek()`: Increments both `currentWeek` and `currentWeekIndex`
- `goToPreviousWeek()`: Decrements both indices
- Max week clamped to `multiWeekPlan.totalWeeks`

**Files Modified:**
- `contexts/TrainingContext.tsx` (imports, state, navigation)

**Commits:** `f8227a6`

---

### Part 4: Integration with Generation Flow (TODO)

**Remaining Tasks:**

1. **Update `generateWeeklyPlan()` function:**
   - Add parameter: `multiWeek: boolean = false`
   - Build `UserTrainingProfile` from `buildPreferencesFromGoals()`
   - Call `generateMultiWeekProgram()` when `multiWeek === true`
   - Update state with `multiWeekPlan` instead of just `weeklyPlan`

2. **Update `selectProgramAndGenerate()`:**
   - Determine multi-week vs single-week based on program template
   - Pass appropriate flag to `generateWeeklyPlan()`

3. **Add helper to build UserTrainingProfile:**
   ```typescript
   function buildUserProfileFromGoals(): UserTrainingProfile {
     // Map GoalWizardContext state to UserTrainingProfile
     // Handle all equipment, fitness level, goals, experience mapping
   }
   ```

4. **Backend API Integration:**
   - Extend `api.saveWorkoutPlan()` to handle multi-week programs
   - Save all weeks to database (not just current week)
   - Update database schema (deferred to Phase 6)

---

### Part 5: Programs.tsx UI Updates (TODO)

**Current State:**
- WorkoutCard now renders (Bug #3 fixed)
- Week navigation UI exists but uses `currentWeek` only

**Remaining Tasks:**

1. **Update week navigation display:**
   - Show "Week X of Y" instead of just "Week X"
   - Disable "Next Week" when at final week
   - Add week progress indicator

2. **Extract current week from multiWeekPlan:**
   ```typescript
   const currentWeek = multiWeekPlan?.weeklyPlans[currentWeekIndex];
   ```

3. **Update WorkoutCalendarCard:**
   - Pass current week's days (not full plan)
   - Ensure dates align with `TrainingDay.calendarDate`

---

## ⏸️ Phase 2: Calendar Integration (NOT STARTED)

**Dependencies:** Phase 1 must be complete

**Tasks:**
1. Add `handleWorkoutBlockComplete()` to DayPlannerContext
2. Update TimeBlockCard swipe handler
3. Sync completion bidirectionally (Planner ↔ Programs)
4. Update `getWorkoutBlocksForDay()` to use `calendarDate`

---

## ⏸️ Phase 3: Multi-Week Calendar Alignment (NOT STARTED)

**Dependencies:** Phase 1 and 2 complete

**Tasks:**
1. Implement auto-navigate to current week on mount
2. Add `getCurrentWeekIndex()` helper
3. Ensure all date logic reads from `TrainingDay.calendarDate`

---

## ⏸️ Phase 4: Equipment Switching (NOT STARTED)

**Dependencies:** Phase 1 complete

**Tasks:**
1. **Exercise-level:** Enhance existing `swapExerciseWithAlternative()`
2. **Day-level:** Add `changeDayEquipment()` function
3. **Program-level:** Add `changeProgramEquipment()` function

---

## ⏸️ Phase 5: Progressive Overload Sync (NOT STARTED)

**Dependencies:** Phase 1 complete

**Tasks:**
1. Update `weightTrackingStorage.ts` for backend-first data flow
2. Implement `saveWeightLog()` with backend sync
3. Implement `getExerciseProgress()` with backend fallback

---

## ⏸️ Phase 6: Database Schema (NOT STARTED)

**Dependencies:** All prior phases complete

**Tasks:**
1. Create PostgreSQL tables (training_programs, program_weeks, program_days, equipment_swaps)
2. Add backend API endpoints
3. Implement program persistence
4. Add workout completion tracking

---

## Known Issues & Limitations

### Current Limitations

1. **Placeholder AI Parsing:**
   - `parseAIProgramOutput()` generates placeholder workouts
   - Need to implement proper GPT response parsing
   - Need to integrate ExerciseDB for alternatives

2. **No Exercise Alternatives:**
   - Current implementation has empty alternatives arrays
   - Need to query ExerciseDB API for 5-8 alternatives per exercise

3. **Single Week Backend Sync:**
   - Only syncs current week to backend
   - Multi-week programs not persisted yet

4. **No Progressive Overload:**
   - Weight recommendations not implemented
   - No week-to-week progression logic

### Future Enhancements

1. **Perplexity Research Integration:**
   - Query latest exercise science research
   - Get program-specific recommendations
   - Validate AI-generated programs against research

2. **AI Day Count Adjustment:**
   - Allow AI to suggest optimal training frequency
   - Adjust based on recovery metrics

3. **Program Templates:**
   - Pre-built programs (PPL, Upper/Lower, Full Body)
   - User can customize before AI generation

---

## Testing Checklist

### Phase 0 Verification (✅ Complete)
- [x] Equipment list appears in AI workout guidance
- [x] Fasting section renders in plan preview
- [x] WorkoutCard displays exercises on Programs tab

### Phase 1 Verification (⏳ In Progress)
- [ ] Complete goal wizard → AI generates 4-week program
- [ ] Programs.tsx shows Week 1 with navigation arrows
- [ ] Navigate to Week 2 → calendar strip updates with new dates
- [ ] Verify `TrainingDay.calendarDate` matches displayed dates

### Phase 2 Verification (Not Started)
- [ ] Open Planner tab → workout blocks appear
- [ ] Swipe workout block → completion syncs to Programs tab
- [ ] Navigate to Programs tab → completed workout shows checkmark

### Phase 3 Verification (Not Started)
- [ ] App opens to current week (not always Week 1)
- [ ] Dates stay aligned across tabs

### Phase 4 Verification (Not Started)
- [ ] Swap individual exercise → alternatives appear
- [ ] Change day equipment → all exercises swap
- [ ] Change program equipment → entire program updates

### Phase 5 Verification (Not Started)
- [ ] Log weight in Programs → appears in Overload tab
- [ ] Same exercise shows same data in both tabs

### Phase 6 Verification (Not Started)
- [ ] Program persists after app restart
- [ ] Completion persists
- [ ] Backend API returns correct data

---

## Next Steps (Immediate)

1. **Implement `buildUserProfileFromGoals()` helper:**
   - Map GoalWizardContext → UserTrainingProfile
   - Handle all field mappings

2. **Update `generateWeeklyPlan()` to call multi-week generator:**
   - Add `multiWeek` parameter
   - Conditionally call `generateMultiWeekProgram()`
   - Update state with `multiWeekPlan`

3. **Test end-to-end flow:**
   - Complete goal wizard
   - Verify 4-week program generates
   - Verify week navigation works

4. **Enhance AI parsing:**
   - Parse actual GPT-4.1-mini response format
   - Extract sets, reps, rest periods
   - Build structured workout objects

5. **Integrate ExerciseDB:**
   - Query for exercise alternatives
   - Populate alternatives arrays
   - Categorize by equipment type

---

## Commits

- `b1e73fb` - Phase 0: Fix critical bugs
- `fa459d5` - Phase 1 Part 1: Type extensions and program generator
- `f8227a6` - Phase 1 Part 2: TrainingContext multi-week support

---

**Last Updated:** February 16, 2026
**Status:** Phase 1 (50% complete) - Types and context updated, need generation integration
