
# Testing Strategy

## Hybrid Testing

Use WebdriverIO for deterministic React UI testing.

Use Computer Use MCP for real desktop interactions.

### WebdriverIO

Preferred for:
- Element selection
- Button interaction
- Form validation
- Navigation
- Assertions
- Repeatable regression tests

### Computer Use

Preferred for:
- Real mouse movement
- Keyboard interaction
- Native dialogs
- Window management
- Screenshot inspection
- Exploratory testing

## Coverage

Always consider:

- Launch
- Navigation
- Forms
- Dialogs
- Menus
- Keyboard
- Focus
- Error handling
- Loading states
- Empty states
- Window resizing
- Persistence

## Selector Priority

1. Accessible role and name
2. Accessible label
3. Stable data-testid
4. Stable text
5. CSS selector
6. Screen coordinates
