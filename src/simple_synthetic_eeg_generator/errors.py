"""Typed fail-closed errors used by the generator transactions."""


class GeneratorError(RuntimeError):
    """Base class for an expected generator refusal."""


class ContractError(GeneratorError):
    """The frozen design or input contract was not met."""


class EnvironmentLockError(GeneratorError):
    """The producing runtime or dependency lock was not exact."""


class ValidationError(GeneratorError):
    """A preregistered candidate gate failed."""


class TransactionError(GeneratorError):
    """A no-overwrite transaction boundary was violated."""
