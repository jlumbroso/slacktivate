
"""
This submodule contains a few helper methods that provide a decorator
:py:func:`slack_retry` that handles all the rate-limiting API exceptions
that are raised by the Slack API and Slack SCIM API packages. This helps
streamline the composition of more complex macros.
"""

import logging
import time
import typing

import backoff
import slack.errors
import slack.web.slack_response
import slack_scim


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "DEFAULT_SECONDS_TO_WAIT",
    "slack_do_we_give_up",
    "slack_retry",
]


SLACK_RATE_LIMITING_STATUS_CODE = 429

SLACK_RATE_LIMITING_ERROR_NAME = "ratelimited"


DEFAULT_SECONDS_TO_WAIT: int = 20
"""
Default number of seconds to wait when a rate limiting exception
is thrown by the Slack API or Slack SCIM API, but without a valid
``Retry-After`` header.
"""


def _do_we_give_up_aux(status_code: int, headers: dict, data: dict = None) -> bool:

    # first determine whether the exception is just rate-limiting (give up: False)
    # or something more serious (give up: True)

    if status_code != SLACK_RATE_LIMITING_STATUS_CODE:

        if data is None:
            # True: give up
            return True

        # if there is data, double check payload to see if it indicates
        # rate limiting (i.e., {'ok': False, 'error': 'ratelimited'})

        if not data.get("ok", True) and data.get("error") == SLACK_RATE_LIMITING_ERROR_NAME:
            pass

        else:
            # True: give up
            return True

    # we've asserted that this is a rate-limiting error
    # so just need to wait
    try:
        time_to_wait = int(headers.get("retry-after", DEFAULT_SECONDS_TO_WAIT))
    except ValueError:
        time_to_wait = DEFAULT_SECONDS_TO_WAIT

    logging.debug("Slack SCIM Rate Limiting: Waiting {} seconds...".format(
        time_to_wait,
    ))

    time.sleep(time_to_wait)

    # False: no need to give up
    return False


def _slack_api_do_we_give_up(err: slack.errors.SlackApiError) -> bool:
    # The slack.errors.SlackApiError contains a SlackResponse object that has
    # the status code and headers we need
    #
    # See documentation or codebase for more information
    # https://api.slack.com/docs/rate-limits
    # https://github.com/slackapi/python-slackclient/blob/1a1f9d05e4653897ba4474a88621cc1482be19b1/slack/errors.py#L18-L33

    response: slack.web.slack_response.SlackResponse = err.response

    return _do_we_give_up_aux(
        status_code=response.status_code,
        headers=response.headers,
        data=response.data,
    )


def _scim_api_do_we_give_up(err: slack_scim.SCIMApiError) -> bool:
    # The slack_scim.SCIMApiError contains two pieces of information that are useful here:
    # - the HTTP status code; if 429, then it indicates a rate limiting error
    # - the full HTTP headers; if it includes a "retry-after" header, then we can wait for that duration
    #
    # See documentation or codebase for more information:
    # https://api.slack.com/scim#ratelimits
    # https://github.com/seratch/python-slack-scim/blob/4c088065b68b7c26c2d2ff7b1e6fad275e1bcd09/src/slack_scim/v1/errors.py#L25-L42

    return _do_we_give_up_aux(
        status_code=err.status,
        headers=err.headers,
    )


def slack_do_we_give_up(
        err: typing.Union[slack.errors.SlackApiError, slack_scim.SCIMApiError, Exception]
) -> bool:

    if isinstance(err, slack.errors.SlackApiError):
        return _slack_api_do_we_give_up(err)

    if isinstance(err, slack_scim.SCIMApiError):
        return _scim_api_do_we_give_up(err)

    # neither one of those exceptions, therefore we should fail
    return True


# Decorator for any call that uses the SCIM API
# see https://api.slack.com/docs/rate-limits
# and https://api.slack.com/scim#ratelimits


slack_retry = backoff.on_exception(
    wait_gen=backoff.constant,

    # multiple exceptions can be provided with a tuple
    # https://docs.python.org/3/tutorial/errors.html#handling-exceptions
    exception=(slack_scim.SCIMApiError, slack.errors.SlackApiError),

    giveup=slack_do_we_give_up
)
"""
.. py:decorator:: @slack_retry
 
    This is a decorator to automatically handle the Slack vendor exceptions,
    :py:exc:`slack.errors.SlackApiError` and :py:exc:`slack_scim.SCIMApiError`
    when it is caused by a rate-limiting error (as described in the
    `Slack API documentation <https://api.slack.com/docs/rate-limits>`_ and the
    `Slack SCIM API documentation <https://api.slack.com/scim#ratelimits>`_.
    When such an exception is thrown, this decorator will pause for an unspecified,
    random amount of time and retry the exact same method call.

.. seealso::
    This functionality is powered by the :py:mod:`backoff` package
    (`available on GitHub <https://github.com/litl/backoff>`_).
"""
