import io
import os
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


@slacktivate.cli.helpers.cli_arg_spec
@slacktivate.cli.helpers.cli_opt_output_format
@click.pass_context
def users_list(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader]=None,
        format: slacktivate.cli.helpers.OutputFormatType="term",
):
    """
    Provide a list of all the users contained in SPEC.
    """
    if spec is not None:
        ctx.obj.set_spec_file(spec_file=spec)

    with click_spinner.spinner(stream=sys.stderr):
        sc_obj = slacktivate.input.config.SlacktivateConfig.from_specification(
            config_data=ctx.obj.specification,
        )

    format = format.lower()

    if format == "term":
        click.echo("\n".join(list(map(lambda x: "{}".format(x), sc_obj.users.keys()))))

    elif format == "csv":

        # NOTE: fix because comma can't (yet) handle missing fields
        lst = list(map(slacktivate.helpers.dict_serializer.to_flat_dict, sc_obj.users.values()))
        lst_ext = slacktivate.helpers.dict_serializer.add_missing_dict_fields(lst)

        import comma
        click.echo(comma.dumps(lst_ext))

    elif format == "json":
        import json
        click.echo(json.dumps(
            obj=sc_obj.users,
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
@click.pass_context
def users_activate(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader],
        dry_run: bool,
):
    """
    Provide a list of all the users contained in SPEC.
    """
    _prep_ctx(ctx=ctx, spec=spec, dry_run=dry_run)

    # MAIN EVENT
    users_created = slacktivate.macros.provision.users_ensure(
        config=ctx.obj.config,
        dry_run=ctx.obj.dry_run,
    )

    if ctx.obj.dry_run:
        logger.info("Users to be created: {}", users_created)
    else:
        logger.info("Users created: {}", users_created)

    click.echo("DONE!")


@slacktivate.cli.helpers.cli_arg_spec
@slacktivate.cli.helpers.cli_opt_dry_run
@click.pass_context
def users_synchronize(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader],
        dry_run: bool,
):
    """
    Synchronize profile information and activation of users in SPEC.
    """
    _prep_ctx(ctx=ctx, spec=spec, dry_run=dry_run)

    # MAIN EVENT
    users_updated = slacktivate.macros.provision.users_update(
        config=ctx.obj.config,
        overwrite_image=None,
        overwrite_name=None,
        dry_run=ctx.obj.dry_run,
    )

    if ctx.obj.dry_run:
        logger.info("Users to be updated: {}", users_updated)
    else:
        logger.info("Users updated: {}", users_updated)

    click.echo("DONE!")
    

@slacktivate.cli.helpers.cli_arg_spec
@slacktivate.cli.helpers.cli_opt_dry_run
@click.pass_context
def users_deactivate(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader],
        dry_run: bool,
):
    """
    Provide a list of all the users contained in SPEC.
    """
    _prep_ctx(ctx=ctx, spec=spec, dry_run=dry_run)

    # MAIN EVENT
    (
        users_to_be_deactivated,
        (count_current_examined,
         count_users_to_be_deactivated,
         count_users_deactivated),
    ) = slacktivate.macros.provision.users_deactivate(
        config=ctx.obj.config,
        dry_run=ctx.obj.dry_run,
    )

    if ctx.obj.dry_run:
        logger.info("Users to be deactivated: {}", users_to_be_deactivated)
    else:
        logger.info("Total users examined: {}", count_current_examined)
        logger.info("Attempted to deactivate: {}", count_users_to_be_deactivated)
        logger.info("Successfully deactivated: {}", count_users_deactivated)

    click.echo("DONE!")

