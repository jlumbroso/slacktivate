
import io
import os
import typing

import click
import click_help_colors

import slacktivate.__version__
import slacktivate.input.parsing


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "chain_functions",

    "SlacktivateCliContextObject",
    "AbstractSlacktivateCliContext",

    "cli_root_group_green",
    "cli_opt_token",
    "cli_opt_spec",
    "cli_opt_dry_run",

    "cli_root",
]


# From: https://stackoverflow.com/a/58005342/408734
def chain_functions(*funcs: typing.List[typing.Callable]) -> typing.Callable:

    def _chain(*args, **kwargs):
        cur_args, cur_kwargs = args, kwargs
        ret = None
        for f in reversed(funcs):
            f = typing.cast(typing.Callable, f)
            cur_args, cur_kwargs = (f(*cur_args, **cur_kwargs), ), {}
            ret = cur_args[0]
        return ret

    return _chain


class SlacktivateCliContextObject:

    _dry_run: bool = False
    _slack_token: typing.Optional[str] = None
    _spec_file: typing.Optional[io.BufferedReader] = None
    _spec_contents: typing.Optional[str] = None
    _specification: typing.Optional[slacktivate.input.parsing.SlacktivateConfigSection] = None

    def __init__(
            self,
            dry_run: typing.Optional[bool] = None,
            slack_token: typing.Optional[str] = None,
            spec_file: typing.Optional[io.BufferedReader] = None,
    ):
        # dry run
        if dry_run is not None:
            self._dry_run = dry_run

        # slack API / scim API token
        self._slack_token = slack_token if slack_token is not None else os.getenv("SLACK_TOKEN")

        # configuration file
        if spec_file is not None:
            self.set_spec_file(spec_file=spec_file)

    def set_spec_file(self, spec_file: io.BufferedReader, no_rewind: bool = True):
        self._spec_file = spec_file

        # cache content
        if self._spec_file is not None:
            if not no_rewind and self._spec_file.seekable():
                self._spec_file.seek(0)

            bin_content = self._spec_file.read()
            try:
                self._spec_contents = bin_content.decode("ascii")
            except UnicodeDecodeError:
                self._spec_contents = bin_content.decode("utf8")

            # flush parsed specification
            self._specification = None

    @property
    def dry_run(self) -> bool:
        return False if self._dry_run is None else self._dry_run

    @property
    def slack_token(self) -> typing.Optional[str]:
        return self._slack_token

    @property
    def spec_filename(self) -> typing.Optional[str]:
        if self._spec_file is not None:
            return self._spec_file.name

    @property
    def spec_contents(self) -> typing.Optional[str]:
        return self._spec_contents

    @property
    def specification(self) -> typing.Optional[slacktivate.input.parsing.SlacktivateConfigSection]:
        if self._spec_contents is not None and self._specification is None:
            try:
                self._specification = slacktivate.input.parsing.parse_specification(
                    contents=self._spec_contents,
                    filename=self.spec_filename,
                )
            except slacktivate.input.parsing.ParsingException:
                return

        if self._specification is not None:
            return self._specification


class AbstractSlacktivateCliContext:

    def __init__(self, ctx_obj):
        self._ctx_obj = ctx_obj

    @property
    def obj(self) -> SlacktivateCliContextObject:
        return self._ctx_obj

    @obj.setter
    def obj(
            self,
            value: typing.Optional[SlacktivateCliContextObject]
    ) -> typing.NoReturn:
        self._ctx_obj = value


cli_root_group_green = click.group(
    cls=click_help_colors.HelpColorsGroup,
    help_headers_color='bright_green',
    help_options_color='green'
)

cli_opt_token = click.option(
    "--token",
    envvar="SLACK_TOKEN", metavar="$SLACK_TOKEN",
    help="Slack API token (requires being an owner or admin)."
)

cli_opt_spec = click.option(
    "--spec",
    type=click.File("rb"),
    default="specification.yaml", envvar="SLACKTIVATE_SPEC", metavar="SPEC",
    help="Provide the specification for the Slack workspace."
)

cli_arg_spec = click.argument(
    "spec",
    type=click.File('rb'),
    default=None, envvar="SLACKTIVATE_CONFIG", metavar="SPEC", required=False,
)

cli_opt_dry_run = click.option(
    "-y", "--dry-run",
    is_flag=True, envvar="SLACKTIVATE_DRY_RUN", default=False,
    help="Do not actually perform the action."
)

cli_opt_version = click.version_option(version=slacktivate.__version__)

OutputFormatType = typing.Union[
    typing.Literal["term"],
    typing.Literal["json"],
    typing.Literal["csv"],
]

cli_opt_output_format = click.option(
    "--format", "-f",
    type=click.Choice(["term", "json", "csv"], case_sensitive=False),
    default="term", metavar="FORMAT",
    help="Output format (e.g.: term, json, csv, ...)"
)


cli_root = chain_functions(*[
    cli_root_group_green,
    cli_opt_token, cli_opt_spec, cli_opt_dry_run, cli_opt_version,
    click.pass_context,
])

