/**
 * Comprehensive Test Suite for GroceryListModal Bug Fixes
 *
 * Verifies all 8 bugs are properly fixed:
 * 1. Infinite loop in budget tier regeneration
 * 2. Race condition in auto-generate effect
 * 3. Stale closure in Select All button
 * 4. Duplicate style definition
 * 5. Missing memoization
 * 6. Unused color parameter
 * 7. Missing React keys
 * 8. Incomplete accessibility
 */

const fs = require('fs');
const path = require('path');

const COMPONENT_PATH = path.join(__dirname, 'HeirclarkHealthAppNew', 'components', 'mealPlan', 'GroceryListModal.tsx');

console.log('🧪 Starting Comprehensive Bug Fix Verification...\n');
console.log('Reading component file:', COMPONENT_PATH);

let fileContent;
try {
  fileContent = fs.readFileSync(COMPONENT_PATH, 'utf8');
} catch (error) {
  console.error('❌ Failed to read component file:', error.message);
  process.exit(1);
}

const results = {
  passed: [],
  failed: [],
  warnings: []
};

function test(bugNumber, description, testFn) {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`Bug #${bugNumber}: ${description}`);
  console.log('='.repeat(80));

  try {
    const result = testFn(fileContent);
    if (result.pass) {
      console.log(`✅ PASSED - ${result.message}`);
      results.passed.push({ bugNumber, description, message: result.message });
    } else {
      console.log(`❌ FAILED - ${result.message}`);
      results.failed.push({ bugNumber, description, message: result.message });
      if (result.details) {
        console.log(`   Details: ${result.details}`);
      }
    }
  } catch (error) {
    console.log(`❌ TEST ERROR - ${error.message}`);
    results.failed.push({ bugNumber, description, message: error.message });
  }
}

// ============================================================================
// Bug #1: Infinite Loop in Budget Tier Regeneration
// ============================================================================
test(1, 'CRITICAL - Infinite loop in budget tier regeneration', (content) => {
  // Check for useRef to track previous budget tier
  const hasRefDeclaration = /const prevBudgetTierRef = useRef\(budgetTier\)/.test(content);

  // Check for proper comparison in useEffect
  const hasProperComparison = /prevBudgetTierRef\.current !== budgetTier/.test(content);

  // Check for ref update
  const hasRefUpdate = /prevBudgetTierRef\.current = budgetTier/.test(content);

  // Check for all dependencies in budget tier useEffect
  const budgetEffectMatch = content.match(/\/\/ Regenerate grocery list[\s\S]*?\}, \[(.*?)\]\);/);
  const dependencies = budgetEffectMatch ? budgetEffectMatch[1].split(',').map(d => d.trim()) : [];

  const hasAllDeps = dependencies.includes('budgetTier') &&
                     dependencies.includes('groceryList') &&
                     dependencies.includes('onGenerateList') &&
                     dependencies.includes('isLoading');

  if (!hasRefDeclaration) {
    return { pass: false, message: 'Missing useRef declaration for prevBudgetTierRef' };
  }

  if (!hasProperComparison) {
    return { pass: false, message: 'Missing comparison check: prevBudgetTierRef.current !== budgetTier' };
  }

  if (!hasRefUpdate) {
    return { pass: false, message: 'Missing ref update: prevBudgetTierRef.current = budgetTier' };
  }

  if (!hasAllDeps) {
    return {
      pass: false,
      message: 'Missing dependencies in budget tier useEffect',
      details: `Found: [${dependencies.join(', ')}]. Expected: budgetTier, groceryList, onGenerateList, isLoading`
    };
  }

  return {
    pass: true,
    message: 'Budget tier useEffect has ref tracking and all dependencies to prevent infinite loop'
  };
});

// ============================================================================
// Bug #2: Race Condition in Auto-Generate Effect
// ============================================================================
test(2, 'CRITICAL - Race condition in auto-generate effect', (content) => {
  // Find auto-generate useEffect
  const autoGenMatch = content.match(/\/\/ Auto-generate grocery list[\s\S]*?\}, \[(.*?)\]\);/);

  if (!autoGenMatch) {
    return { pass: false, message: 'Could not find auto-generate useEffect' };
  }

  const dependencies = autoGenMatch[1].split(',').map(d => d.trim());

  const requiredDeps = ['visible', 'groceryList', 'isLoading', 'onGenerateList', 'budgetTier'];
  const missingDeps = requiredDeps.filter(dep => !dependencies.includes(dep));

  if (missingDeps.length > 0) {
    return {
      pass: false,
      message: 'Auto-generate effect missing dependencies',
      details: `Missing: ${missingDeps.join(', ')}`
    };
  }

  return {
    pass: true,
    message: 'Auto-generate effect has all required dependencies to prevent stale closures'
  };
});

// ============================================================================
// Bug #3: Stale Closure in Select All Button
// ============================================================================
test(3, 'HIGH - Stale closure in Select All button', (content) => {
  // Check for useCallback declaration
  const hasUseCallback = /const handleSelectAll = useCallback\(/.test(content);

  if (!hasUseCallback) {
    return { pass: false, message: 'Select All handler not using useCallback' };
  }

  // Check for proper dependencies
  const callbackMatch = content.match(/const handleSelectAll = useCallback\([\s\S]*?\}, \[(.*?)\]\);/);

  if (!callbackMatch) {
    return { pass: false, message: 'Could not find handleSelectAll useCallback dependencies' };
  }

  const dependencies = callbackMatch[1].split(',').map(d => d.trim());
  const requiredDeps = ['groceryList', 'checkedItems', 'totalItems', 'onToggleItem'];
  const missingDeps = requiredDeps.filter(dep => !dependencies.includes(dep));

  if (missingDeps.length > 0) {
    return {
      pass: false,
      message: 'handleSelectAll missing dependencies',
      details: `Missing: ${missingDeps.join(', ')}`
    };
  }

  // Check that TouchableOpacity uses the callback
  const usesCallback = /onPress={handleSelectAll}/.test(content);

  if (!usesCallback) {
    return { pass: false, message: 'TouchableOpacity not using handleSelectAll callback' };
  }

  return {
    pass: true,
    message: 'Select All button uses useCallback with all required dependencies'
  };
});

// ============================================================================
// Bug #4: Duplicate Style Definition
// ============================================================================
test(4, 'HIGH - Duplicate gradientPill style definition', (content) => {
  // Count occurrences of "gradientPill:"
  const matches = content.match(/gradientPill:\s*{/g);
  const count = matches ? matches.length : 0;

  if (count > 1) {
    return {
      pass: false,
      message: `Found ${count} definitions of gradientPill style (duplicate detected)`
    };
  }

  if (count === 0) {
    return {
      pass: false,
      message: 'No gradientPill style definition found'
    };
  }

  // Verify the remaining definition has borderRadius
  const hasBorderRadius = /gradientPill:\s*{[\s\S]*?borderRadius:\s*16/.test(content);

  if (!hasBorderRadius) {
    return {
      pass: false,
      message: 'gradientPill style missing borderRadius property'
    };
  }

  return {
    pass: true,
    message: 'Only one gradientPill style definition exists with borderRadius'
  };
});

// ============================================================================
// Bug #5: Missing Memoization
// ============================================================================
test(5, 'MEDIUM - Missing memoization for expensive calculations', (content) => {
  // Check for useMemo on totalItems
  const hasTotalItemsMemo = /const totalItems = useMemo\(/.test(content);

  // Check for useMemo on checkedItems
  const hasCheckedItemsMemo = /const checkedItems = useMemo\(/.test(content);

  // Check for useMemo on progress
  const hasProgressMemo = /const progress = useMemo\(/.test(content);

  const failures = [];
  if (!hasTotalItemsMemo) failures.push('totalItems not memoized');
  if (!hasCheckedItemsMemo) failures.push('checkedItems not memoized');
  if (!hasProgressMemo) failures.push('progress not memoized');

  if (failures.length > 0) {
    return {
      pass: false,
      message: 'Missing memoization',
      details: failures.join(', ')
    };
  }

  return {
    pass: true,
    message: 'All expensive calculations (totalItems, checkedItems, progress) are memoized'
  };
});

// ============================================================================
// Bug #6: Unused Color Parameter
// ============================================================================
test(6, 'LOW - Unused color parameter in getCategoryIcon', (content) => {
  // Find getCategoryIcon function definition
  const funcMatch = content.match(/const getCategoryIcon = \((.*?)\) =>/);

  if (!funcMatch) {
    return { pass: false, message: 'Could not find getCategoryIcon function' };
  }

  const params = funcMatch[1];

  // Check if color parameter exists
  if (/color:\s*string/.test(params) || params.includes('color')) {
    return {
      pass: false,
      message: 'getCategoryIcon still has unused color parameter',
      details: `Function signature: ${funcMatch[0]}`
    };
  }

  // Verify it only has category and size
  const expectedSig = /category:\s*string.*size:\s*number/.test(params);

  if (!expectedSig) {
    return {
      pass: false,
      message: 'getCategoryIcon has unexpected signature',
      details: `Found: ${params}`
    };
  }

  return {
    pass: true,
    message: 'getCategoryIcon no longer has unused color parameter'
  };
});

// ============================================================================
// Bug #7: Missing React Keys
// ============================================================================
test(7, 'MEDIUM - Missing keys in conditional renders', (content) => {
  // Check budget tier conditional keys
  const budgetKeySelected = /key={`\$\{tier\}-selected`}/.test(content);
  const budgetKeyUnselected = /key={`\$\{tier\}-unselected`}/.test(content);

  // Check dietary filter conditional keys
  const dietaryKeySelected = /key={`\$\{filter\}-selected`}/.test(content);
  const dietaryKeyUnselected = /key={`\$\{filter\}-unselected`}/.test(content);

  const failures = [];
  if (!budgetKeySelected) failures.push('Budget tier selected key missing');
  if (!budgetKeyUnselected) failures.push('Budget tier unselected key missing');
  if (!dietaryKeySelected) failures.push('Dietary filter selected key missing');
  if (!dietaryKeyUnselected) failures.push('Dietary filter unselected key missing');

  if (failures.length > 0) {
    return {
      pass: false,
      message: 'Missing React keys in conditional renders',
      details: failures.join(', ')
    };
  }

  return {
    pass: true,
    message: 'All conditional renders have proper React keys'
  };
});

// ============================================================================
// Bug #8: Incomplete Accessibility
// ============================================================================
test(8, 'LOW - Incomplete accessibility labels/hints', (content) => {
  // Check for budget tier accessibility hints
  const hasBudgetHints = /accessibilityHint={`Selects \$\{tier\} budget ingredients/.test(content);

  // Check for dietary filter accessibility hints
  const hasDietaryHints = /accessibilityHint={`Filters ingredients to only include/.test(content);

  const failures = [];
  if (!hasBudgetHints) failures.push('Budget tier buttons missing accessibility hints');
  if (!hasDietaryHints) failures.push('Dietary filter buttons missing accessibility hints');

  if (failures.length > 0) {
    return {
      pass: false,
      message: 'Missing accessibility hints',
      details: failures.join(', ')
    };
  }

  return {
    pass: true,
    message: 'All buttons have proper accessibility hints for screen readers'
  };
});

// ============================================================================
// Print Summary
// ============================================================================
console.log('\n' + '='.repeat(80));
console.log('TEST SUMMARY');
console.log('='.repeat(80));

console.log(`\n✅ PASSED: ${results.passed.length} / 8`);
results.passed.forEach(({ bugNumber, description }) => {
  console.log(`   ✓ Bug #${bugNumber}: ${description}`);
});

if (results.failed.length > 0) {
  console.log(`\n❌ FAILED: ${results.failed.length} / 8`);
  results.failed.forEach(({ bugNumber, description, message }) => {
    console.log(`   ✗ Bug #${bugNumber}: ${description}`);
    console.log(`     ${message}`);
  });
}

console.log('\n' + '='.repeat(80));
console.log(`OVERALL: ${results.passed.length === 8 ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED'}`);
console.log('='.repeat(80));

// Exit with appropriate code
process.exit(results.failed.length > 0 ? 1 : 0);
