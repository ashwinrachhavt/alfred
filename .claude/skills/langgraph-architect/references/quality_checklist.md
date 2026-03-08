# LangGraph Code Quality Checklist

## Architecture Quality

### State Design
- [ ] State uses TypedDict with explicit types
- [ ] Messages use `Annotated[list, operator.add]` reducer
- [ ] No unnecessary keys in state
- [ ] State keys have clear, descriptive names
- [ ] Complex state documented with comments

### Graph Topology
- [ ] Clear entry point (START → first node)
- [ ] All paths lead to END
- [ ] No orphan nodes (unreachable)
- [ ] No dead ends (nodes without outgoing edges)
- [ ] Conditional edges have explicit mapping

### Node Functions
- [ ] Single responsibility per node
- [ ] Pure functions where possible (input → output)
- [ ] No side effects except explicit tool calls
- [ ] Return dict with only changed keys
- [ ] Async functions for I/O operations

---

## Error Handling

### Robustness
- [ ] Retry policy on external API nodes
- [ ] Recursion limit configured
- [ ] Tool failures don't crash agent
- [ ] Error state captured for debugging
- [ ] Graceful degradation paths exist

### Validation
- [ ] Required inputs validated early
- [ ] Meaningful error messages
- [ ] Input sanitization where needed
- [ ] Type checking on tool arguments

---

## Tool Management

### Security (Principle of Least Privilege)
- [ ] ALLOWED_TOOLS constant defined
- [ ] Each tool has comment explaining necessity
- [ ] No wildcard tool access
- [ ] Tools filtered at instantiation

### Documentation
- [ ] Tool purposes in system prompt
- [ ] Tool argument schemas clear
- [ ] Tool error behaviors documented
- [ ] Tool dependencies noted (e.g., "needs user_id from X")

---

## Observability

### Debugging Support
- [ ] Actor ID set for tracing
- [ ] Thread ID for session isolation
- [ ] Key decisions logged
- [ ] State transitions visible

### Message Sync (for Rails integration)
- [ ] Uses `_stream_with_sync()` or equivalent
- [ ] User messages synced
- [ ] Assistant messages synced
- [ ] Tool calls visible in conversation

---

## Performance

### Efficiency
- [ ] Minimal tool calls per request
- [ ] Parallel tool calls where independent
- [ ] Avoid redundant LLM calls
- [ ] State size kept reasonable

### Scalability
- [ ] Checkpointing enabled for long workflows
- [ ] Memory cleanup for completed sessions
- [ ] Timeout handling for slow operations

---

## Code Quality

### Readability
- [ ] Clear function names (verb_noun pattern)
- [ ] Docstrings on public methods
- [ ] Complex logic commented
- [ ] Consistent formatting

### Maintainability
- [ ] No hardcoded values (use constants/config)
- [ ] Reusable patterns extracted
- [ ] Clear separation of concerns
- [ ] Tests for critical paths

---

## Project Conventions (agentic/)

### BaseAgent Pattern
- [ ] Extends BaseAgent class
- [ ] Uses `get_instance()` classmethod
- [ ] Implements `execute()` async method
- [ ] Returns proper result dict

### main.py Integration
- [ ] Agent exported in `lois/__init__.py`
- [ ] Route handler in `main.py`
- [ ] InvocationResponse format used
- [ ] Agent type string matches

### System Prompt
- [ ] Clear persona defined
- [ ] Available tools listed with descriptions
- [ ] Step-by-step process documented
- [ ] Output format specified
- [ ] Edge cases addressed

---

## Severity Ratings

### Critical (Must Fix)
- Missing error handling on external calls
- Unbounded recursion possible
- State mutation without reducer
- Security: tool access too broad

### High (Should Fix)
- No retry policy on API calls
- Missing input validation
- Poor error messages
- No observability

### Medium (Consider)
- Verbose state (too many keys)
- Missing documentation
- Inconsistent naming
- Complex conditional logic

### Low (Nice to Have)
- Additional logging
- Performance optimization
- Code style improvements
- Extra test coverage
