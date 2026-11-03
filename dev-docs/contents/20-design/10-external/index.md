# External Design

Of the user-visible behavior, what we keep on purpose without making it a contract in `docs/reference/`, and why. The chapters follow the same units as `docs/reference/`, and only chapters with content are present. Each item is written in the chapter that covers the behavior, wherever it is implemented. So that breaking it is noticed, a test names the heading.

The exception is [Trust Model](70-trust-model.md), which has no corresponding page in `docs/reference/`. It covers a boundary we keep on purpose but do not show the user as a contract.
