"""Provider-independent failures; messages never include prompts or raw bodies."""


class LLMError(Exception):
    """Base inference error."""


class LLMValidationError(LLMError, ValueError):
    pass


class LLMConnectionError(LLMError):
    pass


class LLMTimeoutError(LLMError, TimeoutError):
    pass


class LLMProtocolError(LLMError):
    pass


class LLMHTTPError(LLMError):
    def __init__(self, status):
        self.status = status
        super().__init__("Inference server returned HTTP %s" % status)


class LLMClosedError(LLMError):
    pass


class LLMBusyError(LLMError):
    pass


class LLMUnsupportedFeatureError(LLMError):
    pass
