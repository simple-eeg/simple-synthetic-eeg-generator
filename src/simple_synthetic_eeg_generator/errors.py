"""Typed fail-closed errors used by the generator transactions."""


class GeneratorError(RuntimeError):
    """Base class for an expected generator refusal."""


class ContractError(GeneratorError):
    """The frozen design or input contract was not met."""


class EnvironmentCapabilityError(GeneratorError):
    """The producing runtime lacks a required capability."""


class ValidationError(GeneratorError):
    """A predeclared candidate-independent gate failed."""


class TransactionError(GeneratorError):
    """A no-overwrite transaction boundary was violated."""
