import os
import io
import sys
import textwrap
import typing

import click
import click_help_colors
import click_spinner
import jinja2

import slacktivate.__version__
import slacktivate.cli.commands.channels
import slacktivate.cli.commands.users
import slacktivate.cli.helpers
import slacktivate.cli.logo
import slacktivate.helpers.dict_serializer
import slacktivate.input.config
import slacktivate.input.parsing
import slacktivate.macros.manage
import slacktivate.macros.provision
import slacktivate.slack.classes
import slacktivate.slack.methods


try:
    import dotenv

    if not dotenv.load_dotenv():
        dotenv.load_dotenv(dotenv.find_dotenv())

except ImportError:
    raise


# TODO: implement the following
#
# list users
# list groups
# list channels
# users list
# users deactivate
# users activate
# users synchronize
# groups list
# groups synchronize
# channels list
# channels synchronize
# channels invite --channel "#126-grading-notifications" --group ta126
# validate


@slacktivate.cli.helpers.cli_root
def cli(ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext, token, spec, dry_run):
    ctx.obj = slacktivate.cli.helpers.SlacktivateCliContextObject(
        dry_run=dry_run,
        slack_token=token,
        spec_file=spec,
    )


@cli.command(name="repl")
@slacktivate.cli.helpers.cli_arg_spec
@click.pass_context
def cli_repl(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader],
):
    """
    A Python REPL with the Slacktivate package, and Slack clients loaded
    preconfigured. This is convenient for quick and dirty operations.
    """
    if spec is not None:
        ctx.obj.set_spec_file(spec_file=spec)

    ctx.obj.compile_specification()

    client_api, client_scim = ctx.obj.login()

    header = jinja2.Template(textwrap.dedent("""
        * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
        WELCOME TO SLACKTIVATE v{{ version }}---PYTHON v{{ py_version }} REPL.
        Preloaded object (`help(<obj>)` for documentation; [TAB] for completion):
        - api / scim: Slack API and SCIM clients
        - config: Slacktivate configuration file
        - slacktivate: Slacktivate package
                                                   Made with ❤︎ in Princeton, N.J.
        * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
        """[1:-1])).render(
        version=slacktivate.__version__,
        py_version="{}.{}".format(sys.version_info.major, sys.version_info.minor),
        token=ctx.obj.slack_token)

    footer = "Thanks for using Slacktivate! Please star https://github.com/jlumbroso/slacktivate! ;-)"

    print(slacktivate.cli.logo.SLACK_LOGO_10L)
    print(slacktivate.cli.logo.SLACKTIVATE_LOGO_6L)
    slacktivate.cli.helpers.launch_repl(
        local_vars={
            "api":  client_api,
            "scim": client_scim,
            "spec": ctx.obj.specification,
            "config": ctx.obj.config,

            # helpful symbols to have
            # NOTE: figure out better way to do this
            "User": slacktivate.slack.classes.to_slack_user,
            "Group": slacktivate.slack.classes.to_slack_group,

            "user_patch": slacktivate.slack.methods.user_patch,
            "user_merge": slacktivate.macros.manage.user_merge,
            "users_ensure": slacktivate.macros.provision.users_ensure,
            "users_update": slacktivate.macros.provision.users_update,
            "groups_ensure": slacktivate.macros.provision.groups_ensure,
            "channels_ensure": slacktivate.macros.provision.channels_ensure,
            "slacktivate.macros.manage": slacktivate.macros.manage,
            "slacktivate.macros.provision": slacktivate.macros.provision,

            "users_list": slacktivate.macros.provision.users_list,
            "users_deactivate": slacktivate.macros.provision.users_deactivate,
        },
        header=header,
        footer=footer,
    )


@cli.group(name="list")
@click.pass_context
def cli_list(ctx):
    """
    Lists any type of object defined in the provided specification SPEC,
    which includes users, groups and channels. Using the flag "--slack"
    will provide data on whether the objects have been synchronized with
    the target Slack workspace.
    """
    pass


list_users = cli_list.command(name="users")(slacktivate.cli.commands.users.users_list)


@cli.group(name="users")
@click.pass_context
def cli_users(ctx):
    """
    Sub-command for operations on Slack users (e.g.: activate, deactivate, list, synchronize).
    """
    pass


users_activate = cli_users.command(name="activate")(slacktivate.cli.commands.users.users_activate)
users_deactivate = cli_users.command(name="deactivate")(slacktivate.cli.commands.users.users_deactivate)
users_list = cli_users.command(name="list")(slacktivate.cli.commands.users.users_list)
users_synchronize = cli_users.command(name="synchronize")(slacktivate.cli.commands.users.users_synchronize)

@cli.group(name="channels")
@click.pass_context
def cli_channels(ctx):
    """
    Sub-command for operations on Slack channels (e.g.: list, synchronize, invite).
    """
    pass

#channels_deactivate = cli_channels.command(name="deactivate")(slacktivate.cli.commands.channels.channels_deactivate)
channels_list = cli_channels.command(name="list")(slacktivate.cli.commands.channels.channels_list)
channels_ensure = cli_channels.command(name="ensure")(slacktivate.cli.commands.channels.channels_ensure)

@cli.command()
@slacktivate.cli.helpers.cli_arg_spec
@click.pass_context
def validate(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader]
):
    """
    Validate the configuration file SPEC
    """
    if spec is not None:
        ctx.obj.set_spec_file(spec_file=spec)

    click.secho(
        message="1. Attempting to parse configuration file \"{}\"...  ".format(ctx.obj.spec_filename),
        nl=False,
        err=True,
    )
    try:
        with click_spinner.spinner():
            sc = slacktivate.input.parsing.parse_specification(
                contents=ctx.obj.spec_contents,
                filename=ctx.obj.spec_filename,
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
    click.secho("  Channel definitions: {}".format(len(sc.get("channels", list()))), err=True)
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
    main()
