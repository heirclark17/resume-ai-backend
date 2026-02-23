# Fasting/Eating Window Naming Convention Bug (Fixed Feb 20, 2026)

## Critical Gotcha
GoalWizardContext field names are MISLEADING:
- `fastingStart` = **eating window START** (e.g. '12:00' = noon)
- `fastingEnd` = **eating window END** (e.g. '20:00' = 8 PM)

The UI (NutritionPreferencesStep.tsx) labels this "Eating Window" and displays `{fastingStart} - {fastingEnd}`.

Presets confirm: 16:8 = start:'12:00', end:'20:00'

## What Was Wrong
DayPlannerContext and aiSchedulingService interpreted these literally:
- Treated `fastingEnd` as "when fasting ends" = eating starts → WRONG
- Treated `fastingStart` as "when fasting starts" = eating ends → WRONG
- Constructed eating window as `{start: fastingEnd, end: fastingStart}` = `{start: '20:00', end: '12:00'}` → INVERTED

## Symptoms
- AI rescheduler crammed all meals into 11:15-11:30 AM slot
- All meals conflicted with each other
- Both AI and algorithmic schedulers failed
- Safety net couldn't find conflict-free slots
- 3 meals dropped from timeline every reload

## Files Fixed
- `services/aiSchedulingService.ts` - validation logic + AI prompt
- `services/schedulingEngine.ts` - eating window + fasting block
- `contexts/DayPlannerContext.tsx` - 4 locations (defaults + eating window construction)
- `types/planner.ts` - corrected comments
- `components/agents/habitFormation/HabitFormationCard.tsx` - defaults

## Rule: Always use this mapping
- Eating window start → `fastingStart`
- Eating window end → `fastingEnd`
- Fasting block start (when eating ends) → `fastingEnd`
- Fasting block end (when eating begins) → `fastingStart`
