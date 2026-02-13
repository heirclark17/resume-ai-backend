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
- Onboarding has no program selection step
- NotificationContext was already wired to API

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
