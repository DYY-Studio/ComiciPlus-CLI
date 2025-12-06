import typer, json, pathlib
from rich.console import Console
from urllib.parse import urlsplit

app = typer.Typer(rich_markup_mode="markdown")
console = Console()

@app.command()
def set(
    cookies: str = typer.Option("", help="Path to your cookies.json, should use Cookie-Editor JSON format"),
    proxy: str = typer.Option("", help="Proxy URL"),
    user_agent: str = "",
    host: str = typer.Option("", help="Default host, should be any comic site powered by Comici(コミチ)"),
):
    """
    Write config to `config.json`
    """
    with open("config.json", "r", encoding="utf-8") as f:
        json.dump({
            "cookies": cookies,
            "proxy": proxy,
            "user_agent": user_agent,
            "host": urlsplit(host, "https://").geturl() if host else "",
        }, f, indent=2)
    console.print(f"[green]Config saved to '{pathlib.Path('config.json')}'[/]")

@app.command()
def reset():
    """Delete `config.json` to reset"""
    config = pathlib.Path("config.json")
    if config.exists():
        config.unlink(missing_ok=True)
        console.print(f"[green]Config reset[/]")
    else:
        console.print(f"[yellow]No need to reset, config file not found[/]")

@app.command()
def show():
    """Show content of `config.json`"""
    config = pathlib.Path("config.json")
    if config.exists():
        with open(config, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
    else:
        console.print(f"[yellow]No config found[/]")
        return
    
    console.print(config_dict)