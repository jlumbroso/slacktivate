
import os
import typing

import slack
import slack.errors
import slack_scim


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "SLACK_TOKEN",
    "login",
    "scim",
    "api",
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

# Client to interact with the Slack API <3 <3 <3
# https://api.slack.com/methods
# (using https://github.com/slackapi/python-slackclient)

_slack_client: typing.Optional[slack.WebClient] = None

# Client to interact with the Slack SCIM API <3 <3 <3
# https://api.slack.com/scim
# (using https://github.com/seratch/python-slack-scim)

_slack_scim: typing.Optional[slack_scim.SCIMClient] = None


def login(token: typing.Optional[str] = None, silent_error=False):

    global _slack_client, _slack_scim

    if token is None:
        token = SLACK_TOKEN

    if token is None and not silent_error:
        raise PermissionError(
            "The `SLACK_TOKEN` variable is unset, and no `token` was provided. "
            "Cannot initialize Slack API clients.")

    _slack_client = slack.WebClient(token=token)
    _slack_scim = slack_scim.SCIMClient(token=token)


# try to login
login(token=SLACK_TOKEN, silent_error=True)


def scim(token=None) -> slack_scim.SCIMClient:
    if _slack_scim is None:
        login(token=token or SLACK_TOKEN, silent_error=False)
    return _slack_scim


def api(token=None) -> slack.WebClient:
    if _slack_client is None:
        login(token=token or SLACK_TOKEN, silent_error=False)
    return _slack_client


def find_group_by_display_name(display_name: str) -> slack_scim.Group:
    search_result: slack_scim.Groups = _slack_scim.search_groups(
        filter=f"displayName eq {display_name}",
        count=1
    )

    if search_result is not None and len(search_result.resources) > 0:
        result: slack_scim.Group = search_result.resources[0]
        return result


def list_custom_profile_fields(
        index_by_label: bool = False,
        silent_error: bool = True,
) -> typing.Dict[str, str]:

    # https://api.slack.com/methods/team.profile.get
    try:
        response = _slack_client.team_profile_get()
        if not response.data["ok"]:
            raise slack.errors.SlackApiError(
                message="response failed",
                response=response)

    except slack.errors.SlackApiError as exc:
        if silent_error:
            # empty dictionary
            return dict()
        else:
            raise

    profile_fields = response.data.get("profile", dict()).get("fields")
    if profile_fields is None:
        if silent_error:
            # empty dictionary
            return dict()
        else:
            raise Exception("cannot find expected fields in response (`$.profile.fields`)")

    index = "label" if index_by_label else "id"
    indexed_fields = {
        field[index]: field
        for field in profile_fields
    }

    return indexed_fields


