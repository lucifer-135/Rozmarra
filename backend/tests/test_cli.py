from typer.testing import CliRunner

from rozmarra import __version__
from rozmarra.cli import app

runner = CliRunner()


def test_help_lists_every_command_group():
    result = runner.invoke(app, ["--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    for name in ("data", "twin", "synth", "model", "demo", "serve", "check-language"):
        assert name in result.output


def test_version_option_prints_the_package_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_a_command_that_is_not_built_says_so_and_fails():
    result = runner.invoke(app, ["model", "train"])
    assert result.exit_code == 1
    assert "not built yet" in result.output
