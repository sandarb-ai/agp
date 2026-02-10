# Contributing to AIGP

Thank you for your interest in contributing to the AI Governance Proof (AIGP) specification. AI governance is a new field, and we believe the right format will emerge from real-world use across different industries, regulatory regimes, and agent architectures.

We don't have all the answers. Your perspective — whether you're a regulator, an engineer, a compliance officer, or someone building AI agents — is valuable.

## Ways to Contribute

### Use it and tell us what's missing

If you implement AIGP and find the schema doesn't capture something your regulators need, that's exactly the feedback we want. Open an issue describing:

- What governance action you needed to capture
- What field or event type was missing
- How you worked around it (if you did)

### Propose new event types

The 16 standard types cover what we've seen so far. Healthcare, autonomous vehicles, financial services, and other domains will have governance actions we haven't imagined. To propose a new event type:

1. Follow the `RESOURCE_ACTION` naming convention in `UPPER_SNAKE_CASE`
2. Describe when the event is emitted
3. Note which fields are relevant
4. Open an issue or pull request

### Challenge the design

If you think the schema should be nested instead of flat, or that `governance_hash` should use a Merkle tree, or that events should be signed — open an issue. We'd rather get it right than get it first.

### Build your own implementation

AIGP is Apache 2.0 licensed. Build a Go producer, a Rust consumer, a Spark connector. The more implementations exist, the more useful the format becomes. If you build one, let us know and we'll link to it from the README.

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-proposal`)
3. Make your changes
4. Ensure the JSON Schema validates against your changes (if modifying the schema)
5. Open a pull request with a clear description of what you're proposing and why

## Schema Changes

Changes to the AIGP event schema (`schema/aigp-event.schema.json`) require:

- A clear rationale for why the change is needed
- Backward compatibility analysis (can existing events still validate?)
- At least one example event demonstrating the change
- Updates to the README specification text

## Code of Conduct

Be respectful. Be constructive. Remember that everyone here is trying to solve a hard problem — making AI governance transparent and verifiable. Disagreements about technical approaches are welcome; personal attacks are not.

## Questions?

- [Open an Issue](https://github.com/sandarb-ai/aigp/issues)
- [Start a Discussion](https://github.com/sandarb-ai/aigp/discussions)
- Visit [sandarb.ai/aigp](https://sandarb.ai/aigp) for the web version of the specification
