import os
import io
import sys
import textwrap
import typing

import click
import click_help_colors
import click_spinner
import jinja2
import loguru

import slacktivate.__version__
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


logger = loguru.logger


@slacktivate.cli.helpers.cli_arg_spec
@slacktivate.cli.helpers.cli_opt_output_format
@click.pass_context
def channels_list(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader]=None,
        format: slacktivate.cli.helpers.OutputFormatType="term",
):
    """
    Provide a list of all the channels contained in SPEC.
    """
    if spec is not None:
        ctx.obj.set_spec_file(spec_file=spec)

    with click_spinner.spinner(stream=sys.stderr):
        sc_obj = slacktivate.input.config.SlacktivateConfig.from_specification(
            config_data=ctx.obj.specification,
        )

    format = format.lower()

    if format == "term":
        click.echo("\n".join(list(map(lambda x: "{}".format(x), sc_obj.channels))))

    elif format == "csv":
        
        # FIXME: this is not convincing
        # NOTE: fix because comma can't (yet) handle missing fields
        lst = list(map(slacktivate.helpers.dict_serializer.to_flat_dict, sc_obj.channels))
        lst_ext = slacktivate.helpers.dict_serializer.add_missing_dict_fields(lst)

        import comma
        click.echo(comma.dumps(lst_ext))

    elif format == "json":
        import json
        click.echo(json.dumps(
            obj=sc_obj.channels,
            indent=4,
        ))

def _prep_ctx(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader],
        dry_run: bool,
) -> None:
    if spec is not None:
        ctx.obj.set_spec_file(spec_file=spec)

    if dry_run:
        ctx.obj.activate_dry_run()

    ctx.obj.compile_specification()

    ctx.obj.login()

@slacktivate.cli.helpers.cli_arg_spec
@slacktivate.cli.helpers.cli_opt_dry_run
@click.option(
    "-u", "--kick-unspecified",
    is_flag=True, envvar="SLACKTIVATE_KICK_UNSPECIFIED", default=False,
    help="Kick any user in channels, whose presence is not explicitly specified by the specification."
)
@click.pass_context
def channels_ensure(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader],
        dry_run: bool,
        kick_unspecified: bool,
):
    """
    Ensures the existence of channels and the correctly provisioned
    membership of users in the channels.
    """
    _prep_ctx(ctx=ctx, spec=spec, dry_run=dry_run)

    # MAIN EVENT
    channel_modifications = slacktivate.macros.provision.channels_ensure(
        config=ctx.obj.config,
        remove_unspecified_members=kick_unspecified,
        dry_run=ctx.obj.dry_run,
    )

    import json
    if ctx.obj.dry_run:
        logger.info("channels modifications: {}", json.dumps(channel_modifications, indent=2))
    else:
        logger.info("channels modified: {}", json.dumps(channel_modifications, indent=2))

    click.echo("DONE!")