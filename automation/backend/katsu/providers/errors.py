class ProviderError(ValueError):
    """An actionable provider failure with no secrets in its message."""


class UnknownOutcome(ProviderError):
    """A request might have been billed; never automatically replay it."""
