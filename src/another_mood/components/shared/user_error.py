"""User-facing error base — a user-caused error we can explain, not a bug.

A dependency-free leaf: the diagnostic model, the build-report aggregator,
and the components that raise such errors all depend down on it, so it
sits at the ``shared/`` top level rather than inside either the
``component`` or ``user_source`` package (placing it in either would pull
the other's package into an import cycle).
"""


class UserError(Exception):
    """A user-caused error we can explain — not a bug.

    Classified by ``isinstance`` (not duck typing) so the pipeline
    aggregator and CLI logger render :attr:`user_error_message` as a clean
    message instead of a Python traceback.  A plain ``UserError`` has no
    source-file anchor, so it carries no ``diagnostic_entries``; its
    guidance lives entirely in the message.  Subclasses with a structured
    payload (e.g. ``FileValidationError``) override
    :attr:`user_error_message`.
    """

    @property
    def user_error_message(self) -> str:
        """Human-readable guidance for the user.

        Defaults to the exception's own message; subclasses override when
        they have a richer payload to format.
        """
        return str(self)
