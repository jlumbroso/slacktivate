
"""

"""

import contextlib
import types
import typing
import unittest.mock
import sys

import slack
import slack.errors
import slack_scim

import slacktivate.slack.retry

__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "handle_slack_errors",
    "SlackExceptionHandler",
]


# valid for both the Slack API and Slack SCIM API client
# as of 2020-11-01
SLACK_INTERNAL_API_CALL_METHOD_NAME = "api_call"

RENAMED_METHOD = "_original_{}"


def handle_slack_errors(
        exc_val: Exception,
        exc_type: typing.Optional[typing.Type] = None,
        exc_tb: typing.Optional[types.TracebackType] = None,
) -> bool:
    if exc_type is None:
        exc_type = type(exc_val)

    # if just a return error, then raise, it will be caught by retry
    # decorator if there is one, otherwise user still see it
    retry_error = not slacktivate.slack.retry.slack_do_we_give_up(err=exc_val)
    if retry_error:
        # should be suppressed
        return True

    if issubclass(exc_type, slack.errors.SlackApiError):
        pass

    return False


class SlackExceptionHandler(contextlib.ExitStack):

    _internal_client: typing.Optional[typing.Union[slack_scim.SCIMClient, slack.WebClient]] = None
    _patch_reply_exception: bool = False

    @staticmethod
    def wrap(
            client: typing.Union[slack_scim.SCIMClient, slack.WebClient],
            patch_reply_exception: bool = True,
    ) -> "SlackExceptionHandler":
        return SlackExceptionHandler(
            client=client,
            patch_reply_exception=patch_reply_exception,
        )

    def __init__(
            self,
            client: typing.Union[slack_scim.SCIMClient, slack.WebClient],
            patch_reply_exception: bool = True,
    ):
        super().__init__()

        self._internal_client = client

        if patch_reply_exception:
            _patch_reply_exception = True

            # save the original method
            patch1 = unittest.mock.patch.object(
                self._internal_client,
                RENAMED_METHOD.format(SLACK_INTERNAL_API_CALL_METHOD_NAME),
                getattr(self._internal_client, SLACK_INTERNAL_API_CALL_METHOD_NAME),
                create=True,
            )

            self.enter_context(patch1)

            # wrap it with reply manager
            patch2 = unittest.mock.patch.object(
                self._internal_client,
                SLACK_INTERNAL_API_CALL_METHOD_NAME,
                slacktivate.slack.retry.slack_retry(
                    getattr(
                        self._internal_client,
                        RENAMED_METHOD.format(SLACK_INTERNAL_API_CALL_METHOD_NAME)
                    )
                )
            )

            self.enter_context(patch2)

    def __enter__(self) -> typing.Union[slack_scim.SCIMClient, slack.WebClient]:
        super().__enter__()
        return self._internal_client

    def __exit__(
            self,
            exc_type: type,
            exc_val: typing.Any,
            exc_tb: types.TracebackType,
    ) -> bool:
        ret = handle_slack_errors(
            exc_val=exc_val,
            exc_type=exc_type,
            exc_tb=exc_tb,
        )
        super().__exit__(sys.exc_info())
        return ret
