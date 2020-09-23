import os
import sys

import click
import click_help_colors
import click_spinner

import slacktivate.input.config
import slacktivate.input.parsing


class Repo(object):
    def __init__(self, home=None, debug=False):
        self.home = os.path.abspath(home or '.')
        self.debug = debug

@click.group(
    cls=click_help_colors.HelpColorsGroup,
    help_headers_color='bright_green',
    help_options_color='green'
)
@click.option("--token", envvar="SLACK_TOKEN", metavar="$SLACK_TOKEN", help="Slack API token.")
@click.option('--repo-home', envvar='REPO_HOME', default='.repo')
@click.option('--debug/--no-debug', default=False,
              envvar='REPO_DEBUG')
@click.pass_context
def cli(ctx, token, repo_home, debug):
    ctx.obj = token
    #ctx.obj = Repo(repo_home, debug)


import typing


_ELEMENTARY_TYPE = [int, str, float, bool, type(None)]


def _is_elementary_type(obj):
    for typ in _ELEMENTARY_TYPE:
        if issubclass(type(obj), typ):
            return True
    return False


def to_dict(obj):
    if _is_elementary_type(obj):
        return obj

    if isinstance(obj, list):
        return obj

    if isinstance(obj, dict):
        return {
            key: to_dict(value)
            for (key, value) in obj.items()
        }

    return to_dict(obj.__dict__)


@cli.command()
@click.argument('config', type=click.File('rb'))
@click.pass_context
def validate(ctx, config):
    """
    Validate the configuration file CONFIG
    """
    click.secho(
        message="1. Attempting to parse configuration file \"{}\"...  ".format(config.name),
        nl=False,
        err=True,
    )
    try:
        with click_spinner.spinner():
            sc = slacktivate.input.parsing.parse_specification(
                contents=config.read().decode("ascii"),
                filename=config.name,
            )
    except slacktivate.input.parsing.ParsingException or slacktivate.input.parsing.UserSourceException as exc:
        click.secho("\nERROR: ", nl=False, err=True, fg="red", bold=True)
        click.secho(exc.message, err=True, fg="red")
        sys.exit(1)

    except slacktivate.input.parsing.UserSourceException as exc:
        click.secho("\nERROR: ", nl=False, err=True, fg="red", bold=True)
        click.secho(exc.message, err=True, fg="red")
        sys.exit(1)

    click.secho("DONE!", nl=True, err=True, fg="green", bold=True)

    click.secho(
        message="2. Processing configuration file...  ",
        nl=False,
        err=True,
    )

    with click_spinner.spinner():
        sc_obj = slacktivate.input.config.SlacktivateConfig(config_data=sc)

    click.secho("DONE!", nl=True, err=True, fg="green", bold=True)

    click.secho()
    click.secho("Information:", err=True, bold=True)
    click.secho("  Group definitions: {}".format(len(sc.get("groups", list()))), err=True)
    click.secho("  Channel definitions: {}".format(len(sc.get("groups", list()))), err=True)
    click.secho("  User source:", err=True)
    for source in sc["users"]:
        if "file" in source:
            click.secho("  - {file} (type: '{type}')  ".format(**source), err=True)
    click.secho()
    click.secho("  User count: {}".format(len(sc_obj.users)))
    click.secho("  Group count: {}".format(len(sc_obj.groups)))
    click.secho("  Channel count: {}".format(len(sc_obj.channels)))

    click.secho()


def main():
    return sys.exit(cli())

if __name__ == "__main__":
    main() # pragma: no cover
