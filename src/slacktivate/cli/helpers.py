
import io
import os
import typing

import click
import click_help_colors

import slacktivate.input.parsing


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "SlacktivateCliContext",

]


class SlacktivateCliContext:

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
            self.set_config_file(config_file=spec_file)

    def set_config_file(self, config_file: io.BufferedReader, no_rewind: bool = True):
        self._spec_file = config_file

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
    def specification(self) -> typing.Optional[slacktivate.input.parsing.SlacktivateConfigSection]:
        if self._spec_contents is not None and self._specification is None:
            self._specification = slacktivate.input.parsing.parse_specification(
                contents=self._spec_contents,
                filename=self.spec_filename,
            )

        if self._specification is not None:
            return self._specification


token_decorator = click.option("--token", envvar="SLACK_TOKEN", metavar="$SLACK_TOKEN", help="Slack API token.")
