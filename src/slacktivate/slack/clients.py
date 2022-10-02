
"""
This submodule
"""

import os
import typing

import slack
import slack.errors
import slack_scim

import slacktivate.slack.exceptions


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "SLACK_TOKEN",
    "login",
    "scim",
    "api",
    "managed_scim",
    "managed_api",
]


try:
    import dotenv

    if not dotenv.load_dotenv():
        dotenv.load_dotenv(dotenv.find_dotenv())

except ImportError:
    raise


# Get the slack token from the environment variable
# this token is called the "OAuth Access Token" and instructions to obtain it
# should be contained in this package's README.md

SLACK_TOKEN = os.getenv("SLACK_TOKEN")
"""
In order to use the Slack SCIM API, you need to be an owner of the workspace,
and obtain an API token with ``admin`` scope.

As explained in
`the official Slack SCIM API documentation <https://api.slack.com/scim#access>`_,
the easiest way to obtain a valid token for the purposes of SCIM provisioning
is as follows:

1. As *a Workspace/Organization Owner*, create
   `a new app for your workspace <https://api.slack.com/apps?new_app=1>`_ (see
   `here <https://api.slack.com/start/overview#creating>`_ for the documentation).
2. Add the ``admin`` OAuth scope to
   `the "User Token Scopes" section <https://api.slack.com/authentication/quickstart#configuring>`_.
3. Install the app to your workspace (see
   `here <https://api.slack.com/start/overview#installing_distributing>`_ for
   the documentation).
4. Use the generated token in the "OAuth & Permissions" tab (if you are provided with
   multiple tokens, use the "OAuth Access Token" not the "Bot User OAuth Access Token").

Note that you can easily **reinstall your app** with different permissions if
it turns out you did not select all the necessary permissions.

"""


# Client to interact with the Slack API <3 <3 <3
# https://api.slack.com/methods
# (using https://github.com/slackapi/python-slackclient)

_slack_client: typing.Optional[slack.WebClient] = None

# Client to interact with the Slack SCIM API <3 <3 <3
# https://api.slack.com/scim
# (using https://github.com/seratch/python-slack-scim)

_slack_scim: typing.Optional[slack_scim.SCIMClient] = None


# shortcut to exceptions
SCIMApiError = slack_scim.v1.errors.SCIMApiError


# enum constants for code factor below
_CLIENT_TYPE_API = 0
_CLIENT_TYPE_SCIM = 1


def login(
        token: typing.Optional[str] = None,
        silent_error: bool = False,
        update_global: bool = True,
) -> typing.Tuple[slack.WebClient, slack_scim.SCIMClient]:
    """
    Returns a pair containing a logged-in Slack API and Slack
    SCIM API client.

    :param token: A valid Slack OAuth token (if none is provided,
         will try to obtain it from the environment)

    :param silent_error: Flag whether to silently fail when no valid
        token is available or not

    :param update_global: Flag whether to update the global clients with
        the result of this operation (useful to globally change which
        workspace is being affected by this library)

    :return: A pair containing a properly logged-in Slack API client and
        Slack SCIM API client
    """

    global _slack_client, _slack_scim

    if token is None:
        token = SLACK_TOKEN

    if token is None and not silent_error:
        raise PermissionError(
            "The `SLACK_TOKEN` variable is unset, and no `token` was provided. "
            "Cannot initialize Slack API clients.")

    client_obj = slack.WebClient(token=token)
    scim_obj = slack_scim.SCIMClient(token=token)

    # update global
    if update_global:
        _slack_client = client_obj
        _slack_scim = scim_obj

    return client_obj, scim_obj


# try to login
login(token=SLACK_TOKEN, silent_error=True, update_global=True)


def _generic_client_wrapper(
        token: typing.Optional[str] = None,
        force_login: bool = False,
        update_global: typing.Optional[bool] = None,
        client_id: int = 0,
) -> typing.Union[slack_scim.SCIMClient, slack.WebClient]:

    global _slack_client, _slack_scim

    global_clients = [_slack_client, _slack_scim]

    # if no global client exists, instantiate one
    if _slack_scim is None or force_login:

        # update global by default because default is unset
        local_clients = login(
            token=token or SLACK_TOKEN,
            silent_error=False,
            update_global=update_global if update_global is not None else True,
        )

        return local_clients[client_id]

    # here there is already a global client; two decisions to make:
    # 1. return the global client?
    # 2. if not, then return something else — update the global client?

    if token is None or token == _slack_scim.token:
        return global_clients[client_id]

    # do not update global by default because one already exists
    local_clients = login(
        token=token or SLACK_TOKEN,
        silent_error=False,
        update_global=update_global if update_global is not None else False,
    )

    return local_clients[client_id]


def scim(
        token: typing.Optional[str] = None,
        force_login: bool = False,
        update_global: typing.Optional[bool] = None
) -> slack_scim.SCIMClient:

    return _generic_client_wrapper(
        token=token,
        force_login=force_login,
        update_global=update_global,
        client_id=_CLIENT_TYPE_SCIM,
    )


def api(
        token: typing.Optional[str] = None,
        force_login: bool = False,
        update_global: typing.Optional[bool] = None
) -> slack.WebClient:
    return _generic_client_wrapper(
        token=token,
        force_login=force_login,
        update_global=update_global,
        client_id=_CLIENT_TYPE_API,
    )


def managed_scim(
        token: typing.Optional[str] = None,
        patch_reply_exception: bool = True,
) -> typing.ContextManager[slack_scim.SCIMClient]:
    return slacktivate.slack.exceptions.SlackExceptionHandler.wrap(
        client=scim(token=token, update_global=False),
        patch_reply_exception=patch_reply_exception,
    )


def managed_api(
        token: typing.Optional[str] = None,
        patch_reply_exception: bool = True,
) -> typing.ContextManager[slack.WebClient]:
    return slacktivate.slack.exceptions.SlackExceptionHandler.wrap(
        client=api(token=token, update_global=False),
        patch_reply_exception=patch_reply_exception,
    )
