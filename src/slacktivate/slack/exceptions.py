
import types
import typing

import slack
import slack.errors
import slack_scim

import slacktivate.slack.retry

__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "handle_slack_errors",
    "SlackExceptionHandler",
]


def handle_slack_errors(
        exc_val: Exception,
        exc_type: typing.Optional[typing.Type] = None,
        exc_tb: typing.Optional[types.TracebackType] = None,
) -> bool:
    if exc_type is None:
        exc_type = type(exc_val)

    # if just a return error, then raise, it will be caught by retry
    # decorator if there is one, otherwise user still see it
    retry_error = not slacktivate.slack.retry.slack_give_up_or_retry(err=exc_val)
    if retry_error:
        return False

    if issubclass(exc_type, slack.errors.SlackApiError):
        pass

    return False


class SlackExceptionHandler(typing.ContextManager):

    _internal_client: typing.Optional[typing.Union[slack_scim.SCIMClient, slack.WebClient]] = None

    @staticmethod
    def wrap(client) -> "SlackExceptionHandler":
        return SlackExceptionHandler(client=client)

    def __init__(self, client: typing.Union[slack_scim.SCIMClient, slack.WebClient]):
        self._internal_client = client

    def __enter__(self) -> typing.Union[slack_scim.SCIMClient, slack.WebClient]:
        return self._internal_client

    def __exit__(
            self,
            exc_type: type,
            exc_val: typing.Any,
            exc_tb: types.TracebackType,
    ) -> bool:
        return handle_slack_errors(
            exc_val=exc_val,
            exc_type=exc_type,
            exc_tb=exc_tb,
        )
