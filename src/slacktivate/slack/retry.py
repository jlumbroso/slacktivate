
import logging
import time
import typing

import backoff
import slack.errors
import slack.web.slack_response
import slack_scim


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "slack_retry"
]


def _give_up_or_retry_aux(status_code: int, headers: dict) -> bool:
    if status_code != 429:
        # True: give up
        return True

    # just need to wait
    try:
        time_to_wait = int(headers.get("retry-after", 0))
    except ValueError:
        time_to_wait = 20

    logging.debug("Slack SCIM Rate Limiting: Waiting {} seconds...".format(
        time_to_wait,
    ))

    time.sleep(time_to_wait)

    # False: no need to give up
    return False


def slack_api_give_up_or_retry(err: slack.errors.SlackApiError) -> bool:
    # The slack.errors.SlackApiError contains a SlackResponse object that has
    # the status code and headers we need
    #
    # See documentation or codebase for more information
    # https://api.slack.com/docs/rate-limits
    # https://github.com/slackapi/python-slackclient/blob/1a1f9d05e4653897ba4474a88621cc1482be19b1/slack/errors.py#L18-L33

    response: slack.web.slack_response.SlackResponse = err.response

    return _give_up_or_retry_aux(
        status_code=response.status_code,
        headers=response.headers,
    )


def scim_api_give_up_or_retry(err: slack_scim.SCIMApiError) -> bool:
    # The slack_scim.SCIMApiError contains two pieces of information that are useful here:
    # - the HTTP status code; if 429, then it indicates a rate limiting error
    # - the full HTTP headers; if it includes a "retry-after" header, then we can wait for that duration
    #
    # See documentation or codebase for more information:
    # https://api.slack.com/scim#ratelimits
    # https://github.com/seratch/python-slack-scim/blob/4c088065b68b7c26c2d2ff7b1e6fad275e1bcd09/src/slack_scim/v1/errors.py#L25-L42

    return _give_up_or_retry_aux(
        status_code=err.status,
        headers=err.headers,
    )


def slack_give_up_or_retry(
        err: typing.Union[slack.errors.SlackApiError, slack_scim.SCIMApiError, Exception]
) -> bool:

    if isinstance(err, slack.errors.SlackApiError):
        return slack_api_give_up_or_retry(err)

    if isinstance(err, slack_scim.SCIMApiError):
        return scim_api_give_up_or_retry(err)

    # neither one of those exceptions, therefore we should fail
    return True


# Decorator for any call that uses the SCIM API
# see https://api.slack.com/docs/rate-limits
# and https://api.slack.com/scim#ratelimits

slack_retry = backoff.on_exception(
    wait_gen=backoff.constant,
    exception=slack_scim.SCIMApiError,
    giveup=slack_give_up_or_retry
)
