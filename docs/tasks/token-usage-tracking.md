# Task: Token Usage Tracking per Session

Implement automated token usage tracking for every session using LiteLLM's built-in callback system and persist the aggregated usage to the database after the session finishes.

## Requirements

1.  **Database Persistence**: Store aggregated usage in a new `session_usage` table.
2.  **LiteLLM Integration**: Use LiteLLM's `success_callback` or custom logging handlers.
3.  **Aggregated Tracking**: Track total prompt tokens, completion tokens, and estimated cost per `session_id`.
4.  **Session Finalization**: Save the data to the DB only when the session is finalized (ended).

## Proposed Implementation Plan

### 1. Database Layer
- [ ] Add `SessionUsage` model to `database/models.py`:
    - `id` (UUID, PK)
    - `session_id` (String, Indexed)
    - `total_prompt_tokens` (Integer)
    - `total_completion_tokens` (Integer)
    - `total_cost` (Float/Numeric)
    - `created_at` (TIMESTAMPTZ)
- [ ] Create and run Alembic migration:
    ```bash
    alembic revision --autogenerate -m "create_session_usage_table"
    alembic upgrade head
    ```
- [ ] Add `SessionUsageRepository` to `database/repositories.py`.

### 2. LLM Service Update
- [ ] Update `services/llm_service.py`:
    - Modify `complete` and `complete_with_fallback` signatures to accept an optional `session_id`.
    - Pass `session_id` in the LiteLLM `metadata`:
    ```python
    completion_kwargs = {
        ...,
        "metadata": {"session_id": session_id}
    }
    ```
- [ ] Update callers of `llm_service.complete` (e.g., in `summary_service.py`, `translation_service.py`) to pass the current `session_id`.

### 3. Usage Tracking Logic
- [ ] Implement a custom LiteLLM callback in `services/usage_tracker.py` using `litellm.success_callback`.
- [ ] The callback should:
    - Extract `session_id` from `kwargs["metadata"]`.
    - Update an in-memory accumulator (could be stored in `SessionManager` or a dedicated service).
- [ ] Register the callback:
    ```python
    litellm.success_callback = [my_custom_usage_handler]
    ```

### 4. Finalization
- [ ] Update `SessionManager.finalize` in `services/session_manager.py` to:
    - Retrieve aggregated usage for the `session_id`.
    - Persist the `SessionUsage` record to the database via the repository.
    - Clean up in-memory usage data for that session.

## Success Criteria
- [ ] Every LLM call made during a session is tracked.
- [ ] When a session ends, a record is created in the `session_usage` table.
- [ ] Token counts and costs match LiteLLM's reported usage.
