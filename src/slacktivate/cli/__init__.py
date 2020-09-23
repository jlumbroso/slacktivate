import os
import io
import sys
import typing

import click
import click_help_colors
import click_spinner

import slacktivate.cli.helpers
import slacktivate.input.config
import slacktivate.input.parsing


try:
    import dotenv

    if not dotenv.load_dotenv():
        dotenv.load_dotenv(dotenv.find_dotenv())

except ImportError:
    raise


@click.group(
    cls=click_help_colors.HelpColorsGroup,
    help_headers_color='bright_green',
    help_options_color='green'
)
@click.option(
    "--token",
    envvar="SLACK_TOKEN", metavar="$SLACK_TOKEN",
    help="Slack API token (requires being an owner or admin)."
)
@click.option(
    "--spec",
    type=click.File("rb"),
    default="specification.yaml", envvar="SLACKTIVATE_SPEC", metavar="SPEC",
    help="Provide the specification for the Slack workspace."
)
@click.option(
    "-y", "--dry-run",
    is_flag=True, envvar="SLACKTIVATE_DRY_RUN", default=False,
    help="Do not actually perform the action."
)
@click.pass_context
def cli(ctx, token, spec, dry_run):
    ctx.obj = slacktivate.cli.helpers.SlacktivateCliContext(
        dry_run=dry_run,
        slack_token=token,
        spec_file=spec,
    )


@cli.group(name="list")
@click.argument("config", type=click.File('rb'), envvar="SLACKTIVATE_CONFIG", metavar="CONFIG")
@click.pass_context
def cli_list(ctx):
    pass

@cli_list.group(name="users")
@click.pass_context
def list_users(ctx):
    pass




@cli.command()
@click.argument("spec", type=click.File('rb'), envvar="SLACKTIVATE_SPEC", metavar="SPEC")
@click.pass_context
def validate(ctx, spec):
    """
    Validate the configuration file SPEC
    """
    click.secho(
        message="1. Attempting to parse configuration file \"{}\"...  ".format(spec.name),
        nl=False,
        err=True,
    )
    try:
        with click_spinner.spinner():
            sc = slacktivate.input.parsing.parse_specification(
                contents=spec.read().decode("ascii"),
                filename=spec.name,
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
    main()
