
import code
import io
import os
import sys
import typing

import click
import click_help_colors
import click_spinner
import loguru
import slack
import slack_scim

import slacktivate.__version__
import slacktivate.input.config
import slacktivate.input.parsing
import slacktivate.slack.clients


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "launch_repl",
    "chain_functions",

    "SlacktivateCliContextObject",
    "AbstractSlacktivateCliContext",

    "cli_root_group_green",
    "cli_opt_token",
    "cli_opt_spec",
    "cli_opt_dry_run",

    "cli_root",
]


logger = loguru.logger


# From: https://medium.com/centrality/building-repls-for-fun-and-profit-597ae4fcdd85
def launch_repl(
        local_vars: typing.Optional[typing.Dict[str, typing.Any]] = None,
        header: typing.Optional[str] = None,
        footer: typing.Optional[str] = None
) -> typing.NoReturn:

    no_ipython = True
    try:
        import IPython
        no_ipython = False
    except ImportError or ModuleNotFoundError:
        pass

    if no_ipython:
        import readline
        import rlcompleter
        import slacktivate
        readline.parse_and_bind("tab: complete")

        # thx AnaS Kayed: https://stackoverflow.com/a/63611300/408734
        readline.parse_and_bind("bind ^I rl_complete")

        new_local_vars = {
            "readline": readline,
            "rlcompleter": rlcompleter,
            "slacktivate": slacktivate,
        }
        new_local_vars.update(local_vars)

        readline.set_completer(
            rlcompleter.Completer(new_local_vars).complete
        )

        code.InteractiveConsole(
            locals=new_local_vars,
        ).interact(
            banner=header,
            exitmsg=footer,
        )
    else:
        print(header)
        IPython.start_ipython(
            argv=[],
            user_ns=local_vars
        )
        print(footer)


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
    _slack_token_last_used: typing.Optional[str] = None
    _slacktivate_config: typing.Optional[slacktivate.input.config.SlacktivateConfig] = None
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
        self._slack_token = slack_token

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

    def activate_dry_run(self):
        if self._dry_run is None or not self._dry_run:
            self._dry_run = True

    def compile_specification(self, silent=True, msg=None, **kwargs):

        def do_compile():
            self._slacktivate_config = slacktivate.input.config.SlacktivateConfig.from_specification(
                config_data=self.specification,
            )

        if silent:
            # no I/O
            do_compile()

        else:
            # output to stderr
            if msg is not None:
                click.secho(
                    message=msg,
                    nl=False,
                    err=True,
                    **kwargs,
                )
            with click_spinner.spinner(stream=sys.stderr):
                do_compile()

        return self._slacktivate_config

    def login(self) -> typing.Tuple[slack.WebClient, slack_scim.SCIMClient]:
        logger.debug("CLI: entering login() method")

        # 1. by default use environment variable
        slack_token = os.getenv("SLACK_TOKEN")
        logger.debug("CLI: 1. env variable? SLACK_TOKEN={}", slack_token)

        # trying again with .env file lying around
        try:
            import dotenv
            if not dotenv.load_dotenv():
                dotenv.load_dotenv(dotenv.find_dotenv())
        except ImportError:
            pass

        # 2. may be overriden by .env variable
        slack_token = os.getenv("SLACK_TOKEN") if os.getenv("SLACK_TOKEN") is not None else slack_token
        logger.debug("CLI: 2. load .env? SLACK_TOKEN={}", slack_token)

        # 3. may be overriden by specification.yaml setting
        if self._specification is not None:
            settings_slack_token = self._specification.get("settings", dict()).get("slack_token")
            slack_token = settings_slack_token if settings_slack_token is not None else slack_token
            logger.debug("CLI: 3. specification.yaml? SLACK_TOKEN={}", slack_token)

        # 4. may be overriden by the command line arg
        slack_token = self._slack_token if self._slack_token is not None else slack_token
        logger.debug("CLI: 4. cmd line? SLACK_TOKEN={}", slack_token)

        logger.debug("CLI: concluding with SLACK_TOKEN={}", slack_token)
        self._slack_token_last_used = slack_token

        # Update internally
        if slack_token is not None:
            logger.debug("CLI: exporting SLACK_TOKEN={}", slack_token)
            os.environ["SLACK_TOKEN"] = self._slack_token_last_used
        
        slacktivate.slack.clients.SLACK_TOKEN = self._slack_token_last_used

        clients = slacktivate.slack.clients.login(
            token=self._slack_token_last_used,
            silent_error=False,
            update_global=True,
        )

        # verify workspace
        team_info = None
        try:
            team_info = clients[0].auth_test()
        except Exception as exc:
            logger.error("CLI: failed to login to Slack: {}", exc)
            pass
        
        if team_info is not None and team_info.get("url") is not None:
            team_url = team_info.get("url").lower().strip("/")
            logger.info("CLI: logged in to Slack workspace: {}", team_url)
            
            # check against the workspace URL of the spec (for safety!)

            spec_url = self._specification.get("settings", dict()).get("workspace")

            if spec_url is None:
                logger.debug("CLI: no workspace URL specified in the spec, CANNOT SAFEGUARD ACCESS")
            else:
                spec_url = spec_url.lower().strip("/")
                if spec_url != team_url:
                    logger.error("CLI: workspace URL mismatch: spec={} vs. actual={}", spec_url, team_url)
                    raise RuntimeError("Workspace URL mismatch: spec={} vs. actual={}".format(spec_url, team_url))
                else:
                    logger.debug("CLI: workspace URL matches spec: spec={} vs. actual={}", spec_url, team_url)

        else:
            logger.debug("CLI: failed to login to Slack")

        return clients

    @property
    def config(self) -> slacktivate.input.config.SlacktivateConfig:
        if self._slacktivate_config is None:
            self.compile_specification(
                silent=True,
                msg=None,
            )
        return self._slacktivate_config

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
    metavar="$SLACK_TOKEN",
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

