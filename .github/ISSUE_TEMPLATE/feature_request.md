---
name: Feature Request
about: Propose a new event type, field, or enhancement
title: "[Feature] "
labels: enhancement
assignees: ''
---

## Summary

A concise description of the feature or enhancement.

## Motivation

Why is this needed? What problem does it solve?

## Proposed Change

Describe the change you'd like to see:
- New event type? (follow `RESOURCE_ACTION` naming in `UPPER_SNAKE_CASE`)
- New field? (describe type, whether required/optional, default value)
- New category?

## Example Event

Provide a sample AGP event demonstrating the feature:

```json
{
  "event_id": "...",
  "event_type": "YOUR_NEW_TYPE",
  ...
}
```

## Backward Compatibility

Will this change break existing AGP events?
- [ ] Yes (describe migration path)
- [ ] No (additive change)

## Industry Context

Which industry or use case does this serve? (e.g., healthcare, finance, legal)
