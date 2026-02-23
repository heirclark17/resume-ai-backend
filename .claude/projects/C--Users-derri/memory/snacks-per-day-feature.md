# Snacks Per Day Feature

## Completed: February 23, 2026

### Overview
Added full integration of "snacks per day" preference to the goal wizard, allowing users to select how many snacks they want (0-4 per day), with the preference flowing through to PlanPreviewStep display and AI meal plan generation.

### Implementation Details

#### 1. Frontend State Management
**File**: `contexts/GoalWizardContext.tsx`
- Added `snacksPerDay: number` to WizardState interface
- Added `setSnacksPerDay: (snacks: number) => void` to context
- Default value: 2 snacks per day
- Persisted to AsyncStorage and synced to backend

#### 2. UI Component - Selection
**File**: `components/goals/NutritionPreferencesStep.tsx`
- Added "SNACKS PER DAY" section after "MEALS PER DAY"
- 5 chips for selection: 0, 1, 2, 3, 4 snacks
- Hint text that changes based on selection:
  - 0: "No snacks, main meals only"
  - 1-2: "Light snacking"
  - 3-4: "Frequent snacks between meals"
- Uses haptic feedback on selection
- Styled consistently with meals per day chips

#### 3. UI Component - Display
**File**: `components/goals/PlanPreviewStep.tsx`
- Added Coffee icon import from lucide-react-native
- Added "Snacks Per Day" display section in review step
- Positioned after "Meals Per Day" and before "Intermittent Fasting"
- Uses protein color (#FFB347) for icon and background
- Circle badge showing numeric value (matching meals per day style)

#### 4. Type Definitions
**File**: `types/ai.ts`
- Added `snacksPerDay?: number` to MealPlanPreferences interface
- Positioned after `mealsPerDay` for logical grouping
- Optional field with default fallback (2 snacks)

#### 5. Context Integration
**File**: `contexts/MealPlanContext.tsx`
- Added `snacksPerDay: preferences.snacksPerDay || 2` to aiPreferences object
- Passed to aiService.generateAIMealPlan() via preferences parameter
- Logged in meal plan generation debug output

#### 6. Backend AI Prompt
**File**: `backend/server-complete.js`
- Added line to AI prompt requirements: `- Snacks per day: ${preferences?.snacksPerDay || 2}`
- Updated meal generation instruction:
  - Before: "Include ${preferences?.mealsPerDay || 3} meals per day plus snacks as needed"
  - After: "Include exactly ${preferences?.mealsPerDay || 3} main meals per day (breakfast, lunch, dinner) and ${preferences?.snacksPerDay || 2} snacks per day"
- AI now generates exact number of snacks specified by user

### User Flow
1. User navigates to Nutrition step in goal wizard (step 4/6)
2. User selects how many snacks per day (0-4 chips)
3. User proceeds to Review step
4. PlanPreviewStep displays selected snacks per day with Coffee icon
5. User completes wizard and generates AI meal plan
6. AI generates meal plan with exact number of snacks specified
7. Meal plan displays with user's preferred snack frequency

### Design Decisions
- **Default value**: 2 snacks (moderate snacking, fits most diets)
- **Range**: 0-4 snacks (covers all use cases from zero-snack to frequent grazing)
- **Icon**: Coffee (represents casual eating/break time, universally recognized)
- **Color**: Protein color (#FFB347) - warm orange that stands out from meals (green)
- **Position**: After meals per day, before fasting window (logical meal-related grouping)
- **Backend default**: Falls back to 2 if not set (matches frontend default)

### Files Changed
1. `components/goals/PlanPreviewStep.tsx` - Display and icon import
2. `types/ai.ts` - Type definition
3. `contexts/MealPlanContext.tsx` - Context integration
4. `backend/server-complete.js` - AI prompt update

### Git Commits
1. **Initial Feature** - Commit hash: `4460f3f`
   - Message: "Add snacks per day feature to goal wizard and AI meal generation"

2. **Icon Changes** - Commit hash: `460fc89`
   - Message: "Fix icon import: Replace invalid Bread icon with Wheat"
   - Fixed: Replaced non-existent `Bread` icon with `Wheat` for starches
   - Icons: Grape (snacks), Sprout (vegetables), Wheat (starches), ChefHat (cooking skill)

### Testing Notes
- Selection UI: Verify 0-4 chips selectable with haptic feedback
- Display UI: Verify Coffee icon and numeric badge appear in PlanPreviewStep
- AI Generation: Verify backend logs show snacksPerDay in preferences
- Meal Plan: Verify generated plans include exact number of snacks specified

### Future Enhancements
- Add snack timing preferences (mid-morning, afternoon, evening)
- Add snack macro targets (e.g., protein-focused snacks)
- Add snack type preferences (fruit, nuts, protein bars, etc.)
- Show snack distribution in weekly meal plan summary
