import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OverlyBaseError(Exception):
    ...


class EndSteps(OverlyBaseError):
    ...


class StepError(OverlyBaseError):
    ...


class MalformedStepError(OverlyBaseError):
    ...
