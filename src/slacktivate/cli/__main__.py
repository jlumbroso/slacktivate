import os
import io
import sys
import typing

import click
import click_help_colors
import click_spinner

import slacktivate.cli.helpers
import slacktivate.helpers.dict_serializer
import slacktivate.input.config
import slacktivate.input.parsing


try:
    import dotenv

    if not dotenv.load_dotenv():
        dotenv.load_dotenv(dotenv.find_dotenv())

except ImportError:
    raise


@slacktivate.cli.helpers.cli_root
def cli(ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext, token, spec, dry_run):
    ctx.obj = slacktivate.cli.helpers.SlacktivateCliContextObject(
        dry_run=dry_run,
        slack_token=token,
        spec_file=spec,
    )


@cli.group(name="list")
@click.pass_context
def cli_list(ctx):
    pass


@cli_list.command(name="users")
@slacktivate.cli.helpers.cli_arg_spec
@slacktivate.cli.helpers.cli_opt_output_format
@click.pass_context
def list_users(
        ctx: slacktivate.cli.helpers.AbstractSlacktivateCliContext,
        spec: typing.Optional[io.BufferedReader],
        format: slacktivate.cli.helpers.OutputFormatType,
):
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
