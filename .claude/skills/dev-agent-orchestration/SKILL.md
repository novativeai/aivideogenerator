# Development Agent Orchestration - Multi-Agent Production Pipeline

## Description
A surgical, cost-optimized development pipeline using specialized agents with model selection based on task complexity. Leverages Opus 4.5's orchestration capabilities for critical decisions while delegating appropriately to Sonnet and Haiku for optimal efficiency.

## Model Selection Philosophy

| Model | Use Cases | Cost Factor |
|-------|-----------|-------------|
| **Opus** | Architecture decisions, complex debugging, security-critical code, core planning | High |
| **Sonnet** | Implementation tasks, refactoring, testing, standard coding | Medium |
| **Haiku** | Documentation, searches, text generation, simple queries, Context7 lookups | Low |

## When to Use
- Building new features from scratch
- Major refactoring efforts
- Production deployments
- Dependency updates and migrations
- Performance optimization sprints
- Security hardening

---

## The Development Agent Orchestra

### Phase 1: Intelligence Gathering (Haiku Agents - Run in Parallel)

---

#### Agent 1.1: Context7 Dependency Scanner
**Model:** `haiku`
**Description:** Scan and verify all dependencies

**Prompt:**
```
Using Context7 MCP tools, scan the entire codebase for all dependencies and verify each one:

1. First, use mcp__context7__resolve-library-id to find each library
2. Then use mcp__context7__get-library-docs to check:
   - Current version in package.json/requirements.txt vs latest
   - Breaking changes in newer versions
   - Deprecated APIs being used
   - Security advisories

Focus on:
- Frontend: React, Next.js, Tailwind, Radix UI, and all UI libraries
- Backend: FastAPI, Pydantic, Firebase Admin SDK
- Database: Firebase/Firestore
- Payment: Any payment SDKs
- Auth: Firebase Auth, OAuth libraries

Output a structured report:
| Package | Current | Latest | Status | Breaking Changes | Action Required |
```

---

#### Agent 1.2: Codebase Structure Mapper
**Model:** `haiku`
**Description:** Map codebase architecture

**Prompt:**
```
Map the complete codebase structure:

1. Directory structure and organization
2. Entry points (pages, API routes, main files)
3. Shared utilities and helpers
4. Component hierarchy
5. State management patterns
6. API endpoint inventory
7. Database schema/collections
8. Environment configuration files

Create a structured map that other agents can reference for navigation.
Output as markdown with file trees and relationship diagrams.
```

---

#### Agent 1.3: Existing Pattern Detector
**Model:** `haiku`
**Description:** Detect coding patterns and conventions

**Prompt:**
```
Analyze the codebase to identify established patterns:

1. Naming conventions (files, components, functions, variables)
2. Import organization style
3. Component structure patterns
4. Error handling patterns
5. State management approach
6. API call patterns
7. Styling conventions (CSS, Tailwind classes)
8. TypeScript patterns (types, interfaces, generics usage)
9. Testing patterns if any exist

Document these patterns so implementation agents maintain consistency.
```

---

### Phase 2: Planning (Opus - Sequential)

---

#### Agent 2.1: Architecture Planner
**Model:** `opus`
**Description:** Design implementation architecture

**Prompt:**
```
Based on the intelligence gathered from Phase 1 agents, design the implementation architecture:

1. Review the dependency scan results - plan any necessary updates
2. Review the codebase map - identify optimal locations for new code
3. Review existing patterns - ensure new code follows conventions

Create a detailed implementation plan that includes:
- File locations for new code
- Component/module breakdown
- Data flow design
- API contract design (if applicable)
- State management approach
- Error handling strategy
- Testing strategy

Output as a structured plan with clear phases and dependencies between tasks.
Consider security implications at every decision point.
```

---

#### Agent 2.2: Risk Assessor
**Model:** `opus`
**Description:** Identify risks and edge cases

**Prompt:**
```
Analyze the proposed implementation for risks:

1. Security vulnerabilities that could be introduced
2. Performance bottlenecks
3. Race conditions or async issues
4. Edge cases that need handling
5. Backward compatibility concerns
6. Database migration risks
7. Third-party service dependencies
8. Error scenarios that need graceful handling

For each risk, provide:
- Severity (Critical/High/Medium/Low)
- Mitigation strategy
- Code patterns to avoid
- Testing requirements
```

---

### Phase 3: Implementation (Sonnet Agents - Parallel where possible)

---

#### Agent 3.1: Core Implementation
**Model:** `sonnet`
**Description:** Implement main functionality

**Prompt:**
```
Implement the core functionality as specified in the architecture plan.

Follow these guidelines:
1. Match existing code patterns exactly
2. Use TypeScript with strict typing
3. Include proper error handling for all async operations
4. Add input validation where user data is involved
5. Follow the component/module structure from the plan
6. Keep functions focused and under 50 lines where possible

After implementation:
- Verify all imports are correct
- Ensure no TypeScript errors
- Check that the code integrates with existing patterns
```

---

#### Agent 3.2: API Integration Agent
**Model:** `sonnet`
**Description:** Implement API layer

**Prompt:**
```
Implement the API integration layer:

1. Create/update API routes as specified
2. Add request validation (Pydantic for Python, Zod for TypeScript)
3. Implement proper error responses with appropriate status codes
4. Add rate limiting considerations
5. Include authentication checks where required
6. Add logging for debugging

Ensure:
- All endpoints follow RESTful conventions
- Response types are consistent
- Error messages are user-friendly (not exposing internals)
```

---

#### Agent 3.3: UI Component Agent
**Model:** `sonnet`
**Description:** Implement UI components

**Prompt:**
```
Implement UI components following the design system:

1. Use existing UI components from @/components/ui/
2. Follow Tailwind conventions already in the codebase
3. Ensure responsive design (mobile-first)
4. Add loading states for async operations
5. Add error states with user-friendly messages
6. Implement accessibility (ARIA labels, keyboard navigation)
7. Use the toast notification system for feedback

Component checklist:
- [ ] Props are typed with TypeScript
- [ ] Loading state handled
- [ ] Error state handled
- [ ] Empty state handled (for lists)
- [ ] Responsive on all breakpoints
- [ ] Keyboard accessible
```

---

#### Agent 3.4: State Management Agent
**Model:** `sonnet`
**Description:** Implement state and data flow

**Prompt:**
```
Implement state management following existing patterns:

1. Use React hooks appropriately (useState, useEffect, useCallback, useMemo)
2. Follow existing context patterns if using Context API
3. Implement proper data fetching with loading/error states
4. Add optimistic updates where appropriate
5. Ensure proper cleanup in useEffect
6. Avoid unnecessary re-renders

Patterns to follow:
- Colocate state as close to usage as possible
- Lift state only when necessary
- Use refs for values that don't need re-renders
```

---

### Phase 4: Quality Assurance (Mixed Models - Parallel)

---

#### Agent 4.1: Type Safety Auditor
**Model:** `haiku`
**Description:** Verify TypeScript correctness

**Prompt:**
```
Audit all new/modified code for TypeScript correctness:

1. Run type checking (npx tsc --noEmit)
2. Identify any 'any' types that should be properly typed
3. Check for proper null/undefined handling
4. Verify generics are used correctly
5. Ensure interfaces/types are properly exported
6. Check for type assertions that might be unsafe

Report all issues with file:line references.
```

---

#### Agent 4.2: Security Auditor
**Model:** `opus`
**Description:** Security review of new code

**Prompt:**
```
Perform security audit on all new/modified code:

1. Input validation - is all user input sanitized?
2. Authentication - are all protected routes checking auth?
3. Authorization - are permission checks in place?
4. Data exposure - is sensitive data properly hidden?
5. XSS prevention - is output properly escaped?
6. CSRF protection - are state-changing operations protected?
7. SQL/NoSQL injection - are queries parameterized?
8. Secret handling - are no secrets hardcoded?

For each finding:
- Severity level
- Exact file:line location
- Recommended fix with code example
```

---

#### Agent 4.3: Performance Auditor
**Model:** `sonnet`
**Description:** Performance review

**Prompt:**
```
Audit new code for performance issues:

1. Unnecessary re-renders in React components
2. Missing memoization for expensive computations
3. N+1 query problems in data fetching
4. Large bundle imports that could be lazy loaded
5. Missing image optimization
6. Unoptimized loops or data transformations
7. Memory leaks (missing cleanup, event listeners)

Provide specific fixes with code examples.
```

---

#### Agent 4.4: Test Generator
**Model:** `sonnet`
**Description:** Generate tests for new code

**Prompt:**
```
Generate comprehensive tests for new functionality:

1. Unit tests for utility functions
2. Component tests for UI elements
3. Integration tests for API routes
4. Edge case coverage based on Risk Assessment

Follow existing test patterns in the codebase.
Use Jest/Vitest for unit tests.
Ensure minimum 80% coverage for new code.

Include:
- Happy path tests
- Error scenario tests
- Edge case tests
- Async operation tests
```

---

### Phase 5: Documentation (Haiku - Parallel)

---

#### Agent 5.1: Code Documentation
**Model:** `haiku`
**Description:** Add inline documentation

**Prompt:**
```
Add appropriate documentation to new code:

1. JSDoc comments for exported functions/components
2. Inline comments for complex logic only
3. Type documentation for non-obvious interfaces
4. README updates if new features added

Guidelines:
- Don't over-document obvious code
- Focus on "why" not "what"
- Keep comments concise
- Update any affected existing documentation
```

---

#### Agent 5.2: API Documentation
**Model:** `haiku`
**Description:** Document API changes

**Prompt:**
```
Document any new/modified API endpoints:

1. Endpoint URL and method
2. Request body schema with examples
3. Response schema with examples
4. Error responses and codes
5. Authentication requirements
6. Rate limiting info

Format as OpenAPI/Swagger if project uses it, otherwise markdown.
```

---

### Phase 6: Integration Verification (Opus)

---

#### Agent 6.1: Integration Validator
**Model:** `opus`
**Description:** Final integration check

**Prompt:**
```
Perform final integration validation:

1. Build passes without errors (npm run build / python -m py_compile)
2. All new code integrates with existing systems
3. No regressions in existing functionality
4. Database changes are backward compatible
5. Environment variables are documented
6. Deployment considerations addressed

Run actual build commands and report results.
Create a final checklist for production deployment.
```

---

## Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: INTELLIGENCE                        │
│                      (Haiku - Parallel)                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │   Context7   │ │   Codebase   │ │   Pattern    │            │
│  │   Scanner    │ │    Mapper    │ │   Detector   │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 2: PLANNING                            │
│                    (Opus - Sequential)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Architecture Planner                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                Risk Assessor                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PHASE 3: IMPLEMENTATION                        │
│                    (Sonnet - Parallel)                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │     Core     │ │     API      │ │      UI      │            │
│  │   Implement  │ │ Integration  │ │  Components  │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│                    ┌──────────────┐                             │
│                    │    State     │                             │
│                    │  Management  │                             │
│                    └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PHASE 4: QUALITY                              │
│                   (Mixed - Parallel)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │  Type Safe   │ │   Security   │ │ Performance  │            │
│  │   (Haiku)    │ │   (Opus)     │ │  (Sonnet)    │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│                    ┌──────────────┐                             │
│                    │    Tests     │                             │
│                    │  (Sonnet)    │                             │
│                    └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PHASE 5: DOCUMENTATION                         │
│                    (Haiku - Parallel)                           │
│  ┌──────────────────────┐ ┌──────────────────────┐             │
│  │   Code Documentation │ │   API Documentation  │             │
│  └──────────────────────┘ └──────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE 6: INTEGRATION                            │
│                      (Opus)                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Integration Validator                        │  │
│  │         (Build, Test, Final Checklist)                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference: Agent Launch Commands

### Phase 1 Launch (All Parallel)
```
Launch 3 agents simultaneously with model: haiku
- Agent 1.1: Context7 Dependency Scanner
- Agent 1.2: Codebase Structure Mapper
- Agent 1.3: Existing Pattern Detector
```

### Phase 2 Launch (Sequential)
```
Launch sequentially with model: opus
- Agent 2.1: Architecture Planner (waits for Phase 1)
- Agent 2.2: Risk Assessor (waits for 2.1)
```

### Phase 3 Launch (Parallel)
```
Launch 4 agents simultaneously with model: sonnet
- Agent 3.1: Core Implementation
- Agent 3.2: API Integration Agent
- Agent 3.3: UI Component Agent
- Agent 3.4: State Management Agent
```

### Phase 4 Launch (Parallel)
```
Launch simultaneously with mixed models:
- Agent 4.1: Type Safety Auditor (haiku)
- Agent 4.2: Security Auditor (opus)
- Agent 4.3: Performance Auditor (sonnet)
- Agent 4.4: Test Generator (sonnet)
```

### Phase 5 Launch (Parallel)
```
Launch 2 agents simultaneously with model: haiku
- Agent 5.1: Code Documentation
- Agent 5.2: API Documentation
```

### Phase 6 Launch
```
Launch with model: opus
- Agent 6.1: Integration Validator
```

---

## Cost Optimization Summary

| Phase | Agents | Models | Parallel | Est. Time |
|-------|--------|--------|----------|-----------|
| 1 | 3 | Haiku x3 | Yes | ~30s |
| 2 | 2 | Opus x2 | No | ~2min |
| 3 | 4 | Sonnet x4 | Yes | ~3min |
| 4 | 4 | Mixed | Yes | ~2min |
| 5 | 2 | Haiku x2 | Yes | ~30s |
| 6 | 1 | Opus x1 | N/A | ~1min |

**Total Estimated Time:** ~9 minutes
**Model Distribution:** 5 Haiku, 4 Sonnet, 4 Opus calls

---

## Usage Examples

### Example 1: "Build a new feature"
```
User: "Add a notification preferences page"

1. Launch Phase 1 (Haiku) to understand codebase
2. Launch Phase 2 (Opus) to plan architecture
3. Launch Phase 3 (Sonnet) to implement
4. Launch Phase 4 (Mixed) for quality checks
5. Launch Phase 5 (Haiku) for docs
6. Launch Phase 6 (Opus) for final validation
```

### Example 2: "Update all dependencies"
```
User: "Update all packages to latest versions"

1. Launch Agent 1.1 (Context7 Scanner) only
2. Review breaking changes
3. Launch Phase 2 (Opus) for migration plan
4. Launch targeted Phase 3 agents for updates
5. Launch Phase 4 for regression testing
6. Launch Phase 6 for validation
```

### Example 3: "Quick fix"
```
User: "Fix this bug" (with clear scope)

Skip Phase 1 (already understand codebase)
Skip Phase 2 (simple fix, no architecture needed)
Launch single Sonnet agent for fix
Launch Phase 4.2 (Security) if touching auth/payment
Launch Phase 6 for build validation
```

---

## Notes

- Always gather intelligence before planning
- Opus makes architectural decisions, Sonnet implements, Haiku documents
- Security auditing always uses Opus regardless of feature size
- Context7 should be used to verify ANY library integration
- Parallel execution maximizes speed while maintaining quality
- Each phase's output feeds into the next phase
