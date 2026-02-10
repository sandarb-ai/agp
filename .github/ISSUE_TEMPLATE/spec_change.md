---
name: AIGP Enhancement Proposal (AEP)
about: Propose a change to the AIGP specification
title: "[AEP] "
labels: aep, spec-change
assignees: ''
---

## AEP Title

A short, descriptive title for this enhancement proposal.

## Abstract

A brief (2-3 sentence) summary of the proposed change.

## Motivation

Why is this change needed? What problem does it solve? Reference real-world use cases if possible.

## Specification Change

Describe the exact changes to the AIGP specification:

### Schema Changes
<!-- If modifying the JSON Schema, describe field additions/modifications -->

### Spec Document Changes
<!-- If modifying spec/aigp-spec.md, describe section additions/modifications -->

### Naming Changes
<!-- If modifying AGRN conventions or event type naming -->

## Example Events

Provide example AIGP events that demonstrate the change:

```json
{
  "event_id": "...",
  ...
}
```

## Backward Compatibility

- [ ] This change is backward compatible (existing events still validate)
- [ ] This is a breaking change (describe migration path below)

### Migration Path
<!-- If breaking, how should existing implementations migrate? -->

## Security Considerations

Does this change affect the security properties of AIGP events?

## Privacy Considerations

Does this change introduce new PII or affect data minimization?

## References

- Related issues: #
- Related standards: (e.g., CloudEvents, OpenTelemetry, SPDX)
